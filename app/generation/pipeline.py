"""
End-to-end Widerspruch generation pipeline.

Flow:
  facts + user text
    → RAG retrieve
    → Ollama body
    → style sanitize / no-lists
    → deterministic header
    → citation allowlist repair
    → strong-claim soften
    → polish
    → domain topic guards
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from fastapi import HTTPException

from app.config import (
    DEFAULT_K,
    MAX_K,
    MAX_REPAIR_ROUNDS_CIT,
    MAX_REPAIR_ROUNDS_STRONG,
    NO_STRONG_CLAIMS,
    PREVIEW_CHARS,
    PREVIEW_HARD_CAP,
    STRICT_CITATIONS,
)
from app.generation.compose import compose_letter_enforced_header
from app.generation.guards import (
    dedupe_and_fix_bitte_paragraphs,
    enforce_official_no_lists,
    find_strong_claims,
    guard_remove_anhoerung_para_for_krank_attest,
    guard_remove_work_context_if_not_in_user_text,
    hard_soften_strong_claims,
    remove_klaeger_terms,
    sanitize_widerspruch_text,
)
from app.generation.llm import call_llm
from app.generation.prompts import (
    polish_with_ollama,
    repair_illegal_citations_with_ollama,
    repair_strong_claims_with_ollama,
    widerspruch_body_prompt,
)
from app.jobcenter import hydrate_jobcenter_from_db
from app.rag.citations import (
    allowed_citations_from_items,
    extract_citations,
    repair_remove_illegal_citations,
)
from app.rag.retrieve import build_context, retrieve
from app.utils import safe_str


def extract_user_text(obj: Any) -> str:
    facts = getattr(obj, "facts", None) or {}
    text = (
        (getattr(obj, "text", None) or "")
        or (getattr(obj, "question", None) or "")
        or (facts.get("bescheid_text") or "")
    )
    text = (text or "").strip()
    if not text:
        raise HTTPException(
            422,
            "Missing input text. Provide 'text', 'question' or 'facts.bescheid_text'.",
        )
    return text


def make_preview(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    t = t[:PREVIEW_HARD_CAP]
    limit = max(300, int(PREVIEW_CHARS or 1400))
    if len(t) <= limit:
        return t
    cut = t[:limit]
    last_nl = cut.rfind("\n")
    last_dot = cut.rfind(".")
    best = max(last_nl, last_dot)
    if best > 200:
        cut = cut[: best + 1]
    return cut.rstrip() + "\n\n🔒 Vollständiger Text nach Freischaltung (Download)."


def generate_widerspruch_letter(
    facts: Dict[str, Any],
    req_text: str,
    k: int,
    style: str,
    include_anlagen: bool,
) -> Tuple[str, list, str | None]:
    """Generate a grounded formal letter. Returns (letter, rag_items, context)."""
    facts = hydrate_jobcenter_from_db(facts or {})

    bescheid_datum = safe_str(facts.get("bescheid_datum"))
    query = (
        f"Widerspruch Jobcenter Bescheid {bescheid_datum}. "
        f"Akteneinsicht Zustellung Verwaltungsakt Begründung Minderung Terminversäumnis. "
        f"{req_text[:600]}"
    )
    items = retrieve(query, k=max(2, min(MAX_K, int(k or DEFAULT_K))), require_absatz=True)
    context = build_context(items)

    body = call_llm(widerspruch_body_prompt(context=context, facts=facts, req_text=req_text)).strip()
    if not body:
        raise RuntimeError("LLM returned empty body")

    body = sanitize_widerspruch_text(body)
    body = enforce_official_no_lists(body)

    letter = compose_letter_enforced_header(
        facts=facts, req_text=req_text, body=body, include_anlagen=include_anlagen
    )
    letter = sanitize_widerspruch_text(letter)

    if STRICT_CITATIONS:
        allowed = allowed_citations_from_items(items)
        used = extract_citations(letter)
        illegal = sorted(list(used - allowed))
        if illegal:
            for _ in range(MAX_REPAIR_ROUNDS_CIT):
                fixed = repair_illegal_citations_with_ollama(letter, items=items, illegal=illegal)
                fixed = sanitize_widerspruch_text(fixed)
                used2 = extract_citations(fixed)
                illegal2 = sorted(list(used2 - allowed))
                letter = fixed
                illegal = illegal2
                if not illegal:
                    break
            if illegal:
                letter = repair_remove_illegal_citations(letter, illegal)

    if NO_STRONG_CLAIMS:
        flags = find_strong_claims(letter)
        if flags:
            for _ in range(MAX_REPAIR_ROUNDS_STRONG):
                fixed = repair_strong_claims_with_ollama(letter, flags=flags)
                fixed = sanitize_widerspruch_text(fixed)
                letter = fixed
                flags = find_strong_claims(letter)
                if not flags:
                    break
            if flags:
                letter = hard_soften_strong_claims(letter)

    letter = polish_with_ollama(letter, style=style)
    letter = sanitize_widerspruch_text(letter)
    letter = remove_klaeger_terms(letter)

    parts = letter.split("\nAnlagen:\n", 1)
    head_part = enforce_official_no_lists(parts[0])
    head_part = guard_remove_anhoerung_para_for_krank_attest(head_part, req_text=req_text)
    head_part = sanitize_widerspruch_text(head_part)
    head_part = dedupe_and_fix_bitte_paragraphs(head_part, req_text=req_text)

    if len(parts) == 2:
        letter = head_part + "\n\nAnlagen:\n" + parts[1].strip()
    else:
        letter = head_part

    letter = guard_remove_work_context_if_not_in_user_text(letter, req_text=req_text)
    letter = sanitize_widerspruch_text(letter)

    if STRICT_CITATIONS:
        allowed = allowed_citations_from_items(items)
        used = extract_citations(letter)
        illegal = sorted(list(used - allowed))
        if illegal:
            letter = repair_remove_illegal_citations(letter, illegal)

    if NO_STRONG_CLAIMS:
        flags = find_strong_claims(letter)
        if flags:
            letter = hard_soften_strong_claims(letter)

    letter = sanitize_widerspruch_text(letter)
    letter = remove_klaeger_terms(letter)

    return letter, items, (context if context else None)
