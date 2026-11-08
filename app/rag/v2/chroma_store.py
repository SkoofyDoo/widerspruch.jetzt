"""Shared Chroma access for ingest + hybrid retrieve (project-root data/)."""

from __future__ import annotations

import os
from typing import cast

import chromadb
import numpy as np
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from chromadb.config import Settings
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


class OllamaChromaEmbeddingFunction(EmbeddingFunction[Documents]):
    """LangChain Ollama embeddings with Chroma 1.x ``embed_query(input=...)`` API."""

    def __init__(self, model: str, base_url: str) -> None:
        self._lc = OllamaEmbeddings(model=model, base_url=base_url)

    def __call__(self, input: Documents) -> Embeddings:
        vectors = self._lc.embed_documents(list(input))
        return cast(
            Embeddings,
            [np.asarray(v, dtype=np.float32) for v in vectors],
        )

    def embed_query(self, input: Documents) -> Embeddings:
        # Chroma 1.x calls embed_query(input=<list of query texts>)
        return cast(
            Embeddings,
            [
                np.asarray(self._lc.embed_query(text), dtype=np.float32)
                for text in input
            ],
        )


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
    """Cached Ollama embedding function compatible with Chroma 1.x."""
    global _ef
    if _ef is None:
        _ef = OllamaChromaEmbeddingFunction(
            model=EMBEDDING_MODEL,
            base_url=EMBEDDINGS_BASE_URL,
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
