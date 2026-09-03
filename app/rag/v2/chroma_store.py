"""Shared Chroma access for ingest + hybrid retrieve (project-root data/)."""

from __future__ import annotations

import os

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import create_langchain_embedding
from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings

from app.rag.v2.ingest_config import (
    CHROMA_DIR,
    COLLECTION_METADATA,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    EMBEDDINGS_BASE_URL,
)

load_dotenv()

_ef = None


def get_client():
    """Persistent Chroma client under repo data/chroma."""
    os.makedirs(str(CHROMA_DIR), exist_ok=True)
    print("[CHROMA]: Connection...")
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    print(f"[CHROMA]: Connected {client}")
    return client


def get_embedding():
    """Cached LangChain↔Chroma embedding function (Qwen via Ollama)."""
    global _ef
    if _ef is None:
        _ef = create_langchain_embedding(
            OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=EMBEDDINGS_BASE_URL)
        )
    return _ef


def open_collection(rebuild: bool = False):
    """Open wdjetzt; optionally wipe first for full re-ingest."""
    client = get_client()
    ef = get_embedding()
    if rebuild:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata=COLLECTION_METADATA,
    )
