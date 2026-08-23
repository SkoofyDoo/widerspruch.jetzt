import re
from dotenv import load_dotenv


from langchain_ollama import OllamaEmbeddings
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document


from chroma_store import get_client, open_collection

from ingest_config import  (
    ChunkMeta,
    CLEANED_DIR,
    EMBEDDING_MODEL,
    EMBEDDINGS_BASE_URL,
    MAX_CHARS_ONE_CHUNK,
    ABSATZ_SPLIT,
    CLEANED_GLOB,
    REBUILD,
    EMBED_BATCH_SIZE)


load_dotenv()

print("=" * 70)
print("RAG WITH LANGCHAIN")
print("=" * 70)


#========================================
# Embeddings 
#========================================
# embeddings = OllamaEmbeddings(
#     model = EMBEDDING_MODEL,
#     base_url = EMBEDDINGS_BASE_URL,
# )

# ========================================
# TEXT LOADER
# ========================================
#TODO: Search for new approaches
loader = DirectoryLoader(
    path = str(CLEANED_DIR), 
    glob = str(CLEANED_GLOB),
    loader_cls = TextLoader,
    loader_kwargs = {"encoding": "utf-8"}
    )

documents = loader.load()

print(f"[TEXT LOADER]: Anzahl der Dokumente: {len(documents)}")


# ================================================
# CHUNKING (EIN PARAGRAPH - EIN CHUNK)
# ================================================

def extract_absatz(chunk_text: str) -> str:
    m = re.search(r"\((\d+[a-z]?)\)", chunk_text)
    return f"({m.group(1)})" if m else ""


def chunking(documents: list[Document])-> list[Document]:
    chunks = []
    for doc in documents:
        
        text = doc.page_content.strip()
        base = ChunkMeta.from_document(doc.metadata["source"], text)
        # TODO: Anzahl chars anpassen
        if len(text) <= MAX_CHARS_ONE_CHUNK:
            md = base.as_dict()
            md["absatz"] = ""
            chunks.append(Document(page_content = text, metadata = md))
            continue

        parts = ABSATZ_SPLIT.split(text)
        header = parts[0].strip()
        body = [p.strip() for p in parts[1:] if p.strip()]

        if not body:
            md = base.as_dict()
            chunks.append(Document(page_content = text, metadata = md))
            continue

        for p in body:
            content = f"{header}\n{p}" if header else p
            md = base.as_dict()
            md["absatz"] = extract_absatz(p)
            chunks.append(Document(page_content = content, metadata = md))
    
    print(f"[CHUNKING]: Länge der Chunks {len(chunks)}")
    print(chunks[0].metadata)
    return chunks

    
# TEST
# chunks = chunks[:10]

# ========================================
# CHROMA
# ========================================



def add_chunks(collection, chunks):
    """Chunks und Metadata zur Collection hinzufügen"""
    ids = [f"{c.metadata['source_file']}::{i}" for i, c in enumerate(chunks)]
    print(f"[CHROMA]: indexing {len(ids)} chunks, batch={EMBED_BATCH_SIZE}", flush=True)
    texts = [c.page_content for c in chunks]
    metas = [{
        "source_file": c.metadata["source_file"],
        "law": c.metadata["law"],
        "paragraph": c.metadata["paragraph"],
        "absatz": c.metadata["absatz"],
        }
        for c in chunks
    ]
    for start in range(0, len(ids), EMBED_BATCH_SIZE):
        
        end = start + EMBED_BATCH_SIZE
        collection.add(
            ids = ids[start:end], 
            documents = texts[start:end], 
            metadatas = metas[start:end]
            )
        print(f"[CHROMA]: Embedded: {end}/{len(ids)}")
    
    print(collection.count() == len(chunks))
    return 


def main():
    chunks = chunking(documents)
    collection = open_collection(rebuild=REBUILD)
    if REBUILD or collection.count() == 0:
        add_chunks(collection, chunks)

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
    main()
