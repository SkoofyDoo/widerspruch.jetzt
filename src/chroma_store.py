import os
import chromadb
from pathlib import Path
from dotenv import load_dotenv
from chromadb.config import Settings
from chromadb.utils.embedding_functions import create_langchain_embedding
from langchain_ollama import OllamaEmbeddings

load_dotenv()


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
CLEANED_DIR = DATA_DIR / "cleaned"
CHROMA_DIR = DATA_DIR / "chroma"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen3-embedding:4b")
EMBEDDINGS_BASE_URL = os.getenv("EMBEDDINGS_BASE_URL", "http://127.0.0.1:11434")
REBUILD = False
COLLECTION_NAME = "wdjetzt"
COLLECTION_METADATA = {"hnsw:space" : "cosine"}




# ====================================================
# CHROMA CLIENT
# ====================================================
def get_client():
    """ChromaDB Client"""
    os.makedirs(str(CHROMA_DIR), exist_ok=True)
    print("[CHROMA]: Connection...")
    client = chromadb.PersistentClient(
        path = str(CHROMA_DIR),
        settings = Settings(anonymized_telemetry=False)
    )
    print(f"[CHROMA]: Connected {client}")
    return client

# ====================================================
# CACHED EMBEDDINGS
# ====================================================
_ef = None

def get_embedding():
    global _ef
    if _ef is None:
        _ef = create_langchain_embedding(OllamaEmbeddings(
        model = EMBEDDING_MODEL,
        base_url = EMBEDDINGS_BASE_URL,
    ))
    return _ef


# ====================================================
# OPEN COLLECTION
# ====================================================
def open_collection(rebuild = False):
    """Get or Create Collection"""
    client = get_client()
    ef = get_embedding()
    if rebuild:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        
    return client.get_or_create_collection(
        name = COLLECTION_NAME,
        embedding_function = ef,
        metadata = COLLECTION_METADATA
    )
