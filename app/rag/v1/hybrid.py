"""
Hybrid retriever bridge (Qwen dense + BM25 + RRF) over collection wdjetzt.

Used when RETRIEVER_BACKEND=hybrid. Keeps item shape compatible with
app.rag.retrieve.build_context / citations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from app.config import DEFAULT_K, MAX_K
from app.rag.v1.retrieve import (
    extract_allowed_paragraphs_from_query,
    is_good_chunk,
    is_procedural_query,
    norm_paragraph,
)

from app.rag.v2.chroma_store import open_collection
from app.rag.v2.retriever import build_bm25, dense_search, rrf_fuse, sparse_search

_collection = None
_bm25_pack: Optional[Tuple[Any, list, list, list]] = None

DENSE_N = 30
SPARSE_N = 30


def _state():
    global _collection, _bm25_pack
    if _collection is None:
        _collection = open_collection(rebuild=False)
        if _collection.count() == 0:
            raise RuntimeError(
                "Hybrid collection 'wdjetzt' is empty under data/chroma. "
                "Run: uv run python -m app.rag.v2.ingest  (set INGEST_REBUILD=true if needed)."
            )
        _bm25_pack = build_bm25(_collection)
    return _collection, _bm25_pack


def _keep_chunk(it: dict, require_absatz: bool, procedural: bool) -> bool:
    text = it.get("text") or ""
    if not require_absatz or procedural:
        return True
    if is_good_chunk(text):
        return True
    if (it.get("absatz") or "").strip():
        return True
    if (it.get("paragraph") or "").strip():
        return True
    return False


def _allowed_ok(it: dict, allowed_norm: Optional[Set[str]]) -> bool:
    if allowed_norm is None:
        return True
    mp = norm_paragraph(it.get("paragraph") or "")
    if not mp:
        return True
    return mp in allowed_norm


def _law_priority(law: str, procedural: bool) -> int:
    if not procedural:
        return 0
    if law == "SGG":
        return 0
    if law == "SGB X":
        return 1
    return 2


def retrieve_hybrid(q: str, k: int, require_absatz: bool = True) -> List[dict]:
    """Top-k hybrid retrieval with light procedural / § filters."""
    k = max(1, min(MAX_K, int(k or DEFAULT_K)))
    collection, bm25_pack = _state()
    bm25, ids, docs, metas = bm25_pack

    dense = dense_search(collection, q, n=max(DENSE_N, k * 10))
    sparse = sparse_search(bm25, ids, docs, metas, q, n=max(SPARSE_N, k * 10))
    fused = rrf_fuse(dense, sparse)

    allowed = extract_allowed_paragraphs_from_query(q)
    allowed_norm = {norm_paragraph(a) for a in allowed} if allowed else None
    procedural = is_procedural_query(q)

    picked: List[dict] = []
    seen: Set[str] = set()
    for it in fused:
        cid = it.get("id") or ""
        if cid in seen:
            continue
        if not _keep_chunk(it, require_absatz, procedural):
            continue
        if not _allowed_ok(it, allowed_norm):
            continue
        seen.add(cid)
        row = {
            "id": cid,
            "source_file": it.get("source_file", ""),
            "law": it.get("law", ""),
            "paragraph": it.get("paragraph", ""),
            "absatz": it.get("absatz", ""),
            "distance": float(it.get("distance", 1.0 / (1.0 + float(it.get("rrf_score", 0.0))))),
            "rrf_score": float(it.get("rrf_score", 0.0)),
            "text": it.get("text", ""),
        }
        picked.append(row)

    if procedural:
        picked.sort(
            key=lambda x: (
                _law_priority(x.get("law", ""), True),
                -float(x.get("rrf_score", 0.0)),
            )
        )

    return picked[:k]
