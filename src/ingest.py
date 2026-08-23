import os

import chromadb 
import re
from pathlib import Path
from dotenv import load_dotenv


from langchain_ollama import OllamaEmbeddings
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document
from chromadb.utils.embedding_functions import create_langchain_embedding
from chromadb.config import Settings

load_dotenv()



print("=" * 70)
print("RAG WITH LANGCHAIN")
print("=" * 70)


#========================================
# Embeddings 
#========================================
embeddings = OllamaEmbeddings(
    model = os.environ["EMBEDDING_MODEL"],
    base_url = os.environ["EMBEDDINGS_BASE_URL"]
)


# ========================================
# TEXT LOADER
# ========================================
#TODO: Search for new approaches
loader = DirectoryLoader(
    path = "../data/cleaned/", 
    glob = "sgb*.txt",
    loader_cls = TextLoader,
    loader_kwargs = {"encoding": "utf-8"}
    )

# test_loader = TextLoader(file_path = "../data/cleaned/sgb2__7_SGB_2_-_Einzelnorm.txt", encoding = "utf8")

documents = loader.load()

print(f"[TEXT LOADER]: Anzahl der Dokumente: {len(documents)}")


# ================================================
# METADATA AUS DEM TEXT NAME, GESETZT, PARAGRAPH
# ================================================
def meta_from_source(doc: Document) -> dict:
    source = doc.metadata["source"]
    source_file = Path(source).name
    name = source_file.lower()

    if name.startswith("sgb2__"):
        law = "SGB II"
        m = re.search(r"^sgb2__(\d+[a-z]?)_", source_file, re.I)
    elif name.startswith("sgbx__"):
        law = "SGB X"
        m = re.search(r"__SGBX_(\d+[a-z]?)_", source_file, re.I)
    else:
        law = "UNKNOWN"
        m = None

    paragraph = f"§ {m.group(1)}" if m else ""
    if not paragraph and text:
        m2 = re.search(r"§\s*(\d+[a-z]?)", doc.page_content, re.I)
        if m2:
            paragraph = f"§ {m2.group(1)}"

    return {
        "source": source,
        "source_file": source_file,
        "law": law,
        "paragraph": paragraph,
    }


# ================================================
# CHUNKING (EIN PARAGRAPH - EIN CHUNK)
# ================================================
chunks = []
for doc in documents:
    
    text = doc.page_content.strip()
    meta = meta_from_source(doc)
    # TODO: Anzahl chars anpassen
    if len(text) <= 2000:
        chunks.append(Document(page_content = text, metadata = meta))
        continue

    parts = re.split(r"\n(?=\(\d+[a-z]?\))", text)
    header = parts[0].strip()
    body = [p.strip() for p in parts[1:] if p.strip()]

    if not body:
        chunks.append(Document(page_content = text, metadata = meta))
        continue

    for p in body:
        content = f"{header}\n{p}" if header else p
        chunks.append(Document(page_content = content, metadata = meta))

print(f"[CHUNKING]: Länge der Chunks {len(chunks)}")
# print(chunks[0].page_content)
# print(chunks[0].metadata)
# print("-------")
# print(chunks[1].page_content)
# print(chunks[1].metadata)

# TEST
# chunks = chunks[:10]

# ================================================
# METADATA AUS FÜR CHROMA
# ================================================

ids = [f"{c.metadata['source_file']}::{i}" for i, c in enumerate(chunks)]
texts = [c.page_content for c in chunks]
metas = [{
    "source_file": c.metadata["source_file"],
    "law": c.metadata["law"],
    "paragraph": c.metadata["paragraph"],
    }
    for c in chunks
]


# ========================================
# CHROMA
# ========================================
os.makedirs("../data/chroma/", exist_ok=True)
print("[CHROMA]: Connection..")



client = chromadb.PersistentClient(
    path="../data/chroma",
    settings=Settings(anonymized_telemetry=False)
    )

print(f"[CHROMA]: Connected {client}")

chroma_ef = create_langchain_embedding(embeddings)


try:
    client.delete_collection("wdjetzt")
except Exception:
    pass

print("[CHROMA]: Collection gelöscht")

try:
    collection = client.get_or_create_collection (
        name = "wdjetzt",
        embedding_function = chroma_ef,
        metadata = {"hnsw:space": "cosine"}      
    )
except Exception as e:
    print("[CHROMA]: Collection konnte nicht generiert werden" + e)
    raise  

print(f"[CHROMA]: {collection}, Länge: {collection.count()}")

collection.add(ids = ids, documents = texts, metadatas = metas)

print(f"[CHROMA]: Anzahl: {collection.count()} items wurden hinzugefügt")

print(collection.count() == len(chunks))


query =  (
    "Instruct: Given a question about German social law (SGB II / SGB X), "
    "retrieve the most relevant legal paragraph.\n"
    "Query: Wann ist eine Arbeit unzumutbar?"
)

result = collection.query(
    query_texts = [query], 
    n_results = 3
)

for doc, meta, dist in zip(
    result["documents"][0],
    result["metadatas"][0],
    result["distances"][0],
):
    print(dist, meta)
    print(doc[:400])
    print("---")
                 

if __name__ == "__main__":
    print("Well Done")
