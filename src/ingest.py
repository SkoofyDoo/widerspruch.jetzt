import os

import chromadb 
from dotenv import load_dotenv

from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader

from chromadb.utils.embedding_functions import create_langchain_embedding
from chromadb.config import Settings

load_dotenv()


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
    glob = "**/*.txt",
    loader_cls = TextLoader,
    loader_kwargs = {"encoding": "utf-8"}
    )

# test_loader = TextLoader(file_path = "../data/cleaned/sgb2__7_SGB_2_-_Einzelnorm.txt", encoding = "utf8")

documents = loader.load()

print(f"Anzahl der Dokumente: {len(documents)}")

# ========================================
# TEXT SPLITTER
# ========================================

splitter = RecursiveCharacterTextSplitter(
    chunk_size = 1200,
    chunk_overlap = 150,
    separators = ["\n\n", "\n(", "\n", "\n1", "\n2", ". ", " "]
)

chunks = splitter.split_documents(documents)

# TODO: REPAIR CHUNKING
print(repr(chunks[0].page_content))
print(f"CHUNK 2: {repr(chunks[1].page_content)}")
print("---")

print(f"Anzahl Chunks: {len(chunks)}")

# ========================================
# VECRORE_STORE
# ========================================
# os.makedirs("../data/chroma", exist_ok=True)
# client = chromadb.PersistentClient(
#     path="..data/chroma",
#     settings=Settings(anonymized_telemetry=False)
#     )

# chroma_ef = create_langchain_embedding(embeddings)

# try:
#     client.delete_collection("wdjetzt")
# except Exception:
#     pass

# print(f"[CHROMA]: Collection gelöscht")

# collection = client.create_collection (
#     name = "wdjetzt",
#     embedding_function = chroma_ef,
    
# )
# print(f"[CHROMA]: {collection}, Länge: {collection.count()}")

# for i, d in enumearte:
#     collection.add(ids = d.metadata["source"] + "::" + str(i) , 
#                documents = d.page_content, 
#                metadatas = [{"source" : d.metadata["source"]}]
#                )

# print(f"Anzahl: {collection.count()}")

# print(d.metadata["source"])


# Chroma.from_documents(
#     documents, 
#     embeddings, 
#     persist_directory = "data/chroma", 
#     collection_name = "wdjetzt_embeds")

# ========================================
# 3
# =======================================

if __name__ == "__main__":
    print("Well Done")
