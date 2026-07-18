"""Vector search over the law corpus (debug / demo)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.config import DEFAULT_K, E5_QUERY_PREFIX, MAX_K
from app.deps import get_collection
from app.models import SearchHit
from app.utils import strip_passage_prefix

router = APIRouter(tags=["search"])


@router.get("/search", response_model=list[SearchHit])
def search(q: str = Query(..., min_length=2), k: int = Query(DEFAULT_K, ge=1, le=MAX_K)):
    """Return top-k vector hits (no letter generation)."""
    col = get_collection()
    res = col.query(
        query_texts=[E5_QUERY_PREFIX + q],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    hits = []
    for i in range(len(res["ids"][0])):
        text = strip_passage_prefix(res["documents"][0][i])
        md = res["metadatas"][0][i] or {}
        hits.append(
            SearchHit(
                id=res["ids"][0][i],
                score=float(res["distances"][0][i]),
                text=text,
                source_file=md.get("source_file", ""),
                law=md.get("law", ""),
                paragraph=md.get("paragraph", ""),
            )
        )
    return hits
