"""Lazy infrastructure dependencies (Chroma collection, optional Stripe)."""

from __future__ import annotations

from typing import Any, Optional

from app.config import CHROMA_DIR, COLLECTION, EMBEDDING_MODEL

try:
    import stripe as stripe_mod
except Exception:  # pragma: no cover
    stripe_mod = None

stripe = stripe_mod

_client: Any = None
_col: Any = None
_embed_fn: Any = None
_init_error: Optional[str] = None


def get_embed_fn():
    global _embed_fn
    if _embed_fn is None:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

        _embed_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    return _embed_fn


def get_collection():
    """Return the Chroma collection, loading it on first use."""
    global _client, _col, _init_error
    if _col is not None:
        return _col
    if _init_error:
        raise RuntimeError(_init_error)
    try:
        import chromadb

        _client = chromadb.PersistentClient(path=CHROMA_DIR)
        _col = _client.get_collection(name=COLLECTION, embedding_function=get_embed_fn())
        return _col
    except Exception as e:
        _init_error = (
            f"Chroma collection '{COLLECTION}' not found or failed to load. "
            f"CHROMA_DIR='{CHROMA_DIR}'. Run: python src/index.py. Original error: {e}"
        )
        raise RuntimeError(_init_error) from e


def chroma_status() -> dict:
    """Best-effort health details without raising."""
    try:
        col = get_collection()
        return {"chroma_ok": True, "collection": COLLECTION, "chunks": col.count()}
    except Exception as e:
        return {
            "chroma_ok": False,
            "collection": COLLECTION,
            "chunks": 0,
            "error": str(e),
        }
