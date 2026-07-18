"""Vector retrieval over SGB II / SGB X chunks with procedural bias."""

from __future__ import annotations

import re
from typing import List, Optional, Set

from app.config import (
    DEFAULT_K,
    DISTANCE_CUTOFF,
    E5_QUERY_PREFIX,
    MAX_K,
    RAG_OVERSAMPLE,
)
from app.deps import get_collection
from app.utils import strip_passage_prefix

PROC_KEYWORDS = [
    "bescheid", "widerspruch", "anhörung", "akteneinsicht", "frist", "zustellung",
    "verwaltungsakt", "begründung", "formfehler", "verfahrensfehler", "überprüfung",
    "rücknahme", "widerruf", "sozialgericht", "eilantrag", "aufschiebende wirkung",
    "wiedereinsetzung",
]


def is_procedural_query(q: str) -> bool:
    ql = (q or "").lower()
    return any(k in ql for k in PROC_KEYWORDS)


def extract_allowed_paragraphs_from_query(q: str) -> Optional[Set[str]]:
    m = re.search(r"§\s*(\d+[a-z]?)", q, flags=re.IGNORECASE)
    if not m:
        return None
    wanted = m.group(1).lower()
    allowed = {wanted, f"§ {wanted}"}
    if wanted in {"31", "31a", "31b", "32"}:
        for x in ["31", "31a", "31b", "32"]:
            allowed.add(x)
            allowed.add(f"§ {x}")
    return allowed


def is_good_chunk(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return ("(1)" in t) or ("(2)" in t) or ("(3)" in t)


def norm_paragraph(p: str) -> str:
    p = (p or "").strip().lower()
    if not p:
        return ""
    return p.replace("§", "").strip()


def _collect_items_from_res(res, q: str, allowed, require_absatz: bool, k: int, seen: set, existing=None):
    items = list(existing or [])
    ids = res.get("ids", [[]])[0]
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    procedural = is_procedural_query(q)

    allowed_norm = {norm_paragraph(a) for a in (allowed or set())} if allowed is not None else None

    for i in range(min(len(ids), len(docs))):
        dist = float(dists[i]) if i < len(dists) else 999.0
        if dist > DISTANCE_CUTOFF:
            continue

        meta = metas[i] or {}
        text = strip_passage_prefix(docs[i])

        if require_absatz and (not is_good_chunk(text)) and (not procedural):
            continue

        if allowed_norm is not None:
            mp = (meta.get("paragraph") or "").strip()
            mp_norm = norm_paragraph(mp)
            if mp_norm and mp_norm not in allowed_norm:
                continue

        key = (meta.get("law", ""), meta.get("paragraph", ""), meta.get("source_file", ""), text[:140])
        if key in seen:
            continue
        seen.add(key)

        items.append({
            "id": ids[i],
            "source_file": meta.get("source_file", ""),
            "law": meta.get("law", ""),
            "paragraph": meta.get("paragraph", ""),
            "distance": dist,
            "text": text,
        })
        if len(items) >= k:
            break

    return items


def retrieve(q: str, k: int, require_absatz: bool = True) -> List[dict]:
    """Retrieve top-k grounded law chunks for a user query."""
    col = get_collection()
    k = max(1, min(MAX_K, int(k or DEFAULT_K)))
    take = max(60, k * RAG_OVERSAMPLE)
    allowed = extract_allowed_paragraphs_from_query(q)
    procedural = is_procedural_query(q)

    def _run_query(where=None, take_n=take):
        return col.query(
            query_texts=[E5_QUERY_PREFIX + q],
            n_results=take_n,
            include=["documents", "metadatas", "distances"],
            where=where,
        )

    items = []
    seen = set()

    if procedural:
        try:
            res1 = _run_query(where={"law": "SGB X"}, take_n=take)
            items = _collect_items_from_res(res1, q, allowed, require_absatz, k, seen, existing=items)
            if len(items) >= k:
                return items
        except Exception:
            pass

    res2 = _run_query(where=None, take_n=take)
    items = _collect_items_from_res(res2, q, allowed, require_absatz, k, seen, existing=items)
    return items


def build_context(items) -> str:
    return "\n\n".join(
        f"[{it.get('law', '')} {it.get('paragraph', '')} | {it['id']} | {it['source_file']}]\n{it['text']}"
        for it in items
    )


def extract_title_from_text(text: str) -> str:
    t = (text or "").replace("\n", " ").strip()
    if not t:
        return ""
    m = re.search(
        r"\b§\s*\d+[a-z]?\b.*?\bSGB\s*X\b\s+(.+?)(?:\(\s*1\s*\)|\(\s*2\s*\)|\(\s*3\s*\)|$)",
        t,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1).strip(" -:;,.")[:120]
    m2 = re.search(
        r"\b§\s*\d+[a-z]?\b\s+(.+?)(?:\(\s*1\s*\)|\(\s*2\s*\)|\(\s*3\s*\)|$)",
        t,
        flags=re.IGNORECASE,
    )
    if m2:
        title = m2.group(1).strip(" -:;,.")
        title = re.sub(r"^SGB\s*X\s+", "", title, flags=re.IGNORECASE).strip()
        return title[:120]
    return ""


def build_quellen_unique(items, max_cites: int = 8):
    best = {}
    for it in items or []:
        law = (it.get("law") or "").strip()
        par = (it.get("paragraph") or "").strip()
        if not law and not par:
            continue
        key = (law, par)
        if key not in best or float(it.get("distance", 999)) < float(best[key].get("distance", 999)):
            best[key] = it
    ranked = sorted(best.values(), key=lambda x: float(x.get("distance", 999)))
    out = []
    for it in ranked[:max_cites]:
        out.append({
            "law": it.get("law", ""),
            "paragraph": it.get("paragraph", ""),
            "title": extract_title_from_text(it.get("text", "")),
            "source_file": it.get("source_file", ""),
            "distance": it.get("distance", None),
        })
    return out
