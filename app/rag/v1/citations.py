"""Citation allowlist / extract / hard-repair for grounded legal references."""

from __future__ import annotations

import re
from typing import List, Set

from app.utils import normalize_citation_order

_CIT_RE = re.compile(
    r"(?:§\s*\d+[a-z]?)\s*(?:SGB\s*(?:I{1,3}|IV|V|VI|VII|VIII|IX|X|XI|XII|II|2))",
    flags=re.IGNORECASE,
)


def norm_citation(c: str) -> str:
    c = (c or "").strip()
    c = re.sub(r"\s+", " ", c)
    c = c.replace("SGB 2", "SGB II")
    return c.upper()


def extract_citations(text: str) -> Set[str]:
    """Return normalized § citations found in free text."""
    if not text:
        return set()
    found = set()
    t = normalize_citation_order(text)
    for m in _CIT_RE.finditer(t):
        found.add(norm_citation(m.group(0)))
    return found


def allowed_citations_from_items(items) -> Set[str]:
    """Build allowlist of citations that appear in retrieved RAG chunks."""
    out = set()
    for it in items or []:
        law = (it.get("law") or "").strip()
        par = (it.get("paragraph") or "").strip()
        if not law or not par:
            continue
        par2 = par.strip() if par.strip().startswith("§") else "§ " + par.strip()
        out.add(norm_citation(f"{par2} {law}"))
    return out


def repair_remove_illegal_citations(text: str, illegal: List[str]) -> str:
    """Deterministic fallback: strip illegal citations from the letter."""
    t = text or ""
    t = normalize_citation_order(t)
    for cit in illegal:
        m = re.search(r"§\s*(\d+[A-Z]?)\s*SGB\s*([A-Z0-9]+)", cit, flags=re.IGNORECASE)
        if not m:
            continue
        num = m.group(1)
        book = m.group(2)
        pat = re.compile(rf"§\s*{re.escape(num)}\s*SGB\s*{re.escape(book)}", flags=re.IGNORECASE)
        t = pat.sub("", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()
