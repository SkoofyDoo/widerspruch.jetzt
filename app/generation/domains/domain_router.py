from __future__ import annotations

from dataclasses import dataclass

from app.generation.domains.packs import DOMAINS, DomainPack, get_pack

@dataclass(frozen=True)
class DomainDecision:
    domain_id: str
    confidence: float
    reason: str
    pack: DomainPack
    
def detect_domain(user_text: str, facts: dict | None = None) -> DomainDecision:
    """Правило-based router. Позже можно добавить LLM-fallback."""
    text = (user_text or "").lower()
    facts = facts or {}

    # явный сигнал Jobcenter из фактов/текста
    jc_hint = any(
        w in text
        for w in ("jobcenter", "bürgergeld", "alg ii", "sgb ii", "bedarfsgemeinschaft")
    ) or bool(facts.get("jobcenter_name") or facts.get("jobcenter_id"))

    scores: dict[str, int] = {}
    for domain_id, pack in DOMAINS.items():
        if domain_id == "generic":
            continue
        score = 0
        for kw in pack.keywords:
            if kw in text:
                score += 1
        if score:
            scores[domain_id] = score

    # внутри Jobcenter предпочитаем более специфичные домены
    if scores:
        # если нет jc_hint, но сработали jobcenter_* keywords — всё равно ок
        best_id = max(scores, key=lambda k: (scores[k], _specificity(k)))
        best_score = scores[best_id]
        total = sum(scores.values()) or 1
        confidence = min(0.95, 0.45 + best_score / max(3, total))
        return DomainDecision(
            domain_id=best_id,
            confidence=confidence,
            reason=f"keyword hits={scores}",
            pack=get_pack(best_id),
        )

    if jc_hint:
        return DomainDecision(
            domain_id="jobcenter_general",
            confidence=0.7,
            reason="jobcenter hint without specific subtype",
            pack=get_pack("jobcenter_general"),
        )

    return DomainDecision(
        domain_id="generic",
        confidence=0.4,
        reason="no domain keywords matched",
        pack=get_pack("generic"),
    )


def _specificity(domain_id: str) -> int:
    """При равном score берём более узкий домен."""
    order = {
        "jobcenter_termin": 3,
        "jobcenter_minderung": 3,
        "jobcenter_kdu": 3,
        "jobcenter_general": 1,
        "generic": 0,
    }
    return order.get(domain_id, 0)


def build_domain_query(req_text: str, bescheid_datum: str, pack: DomainPack) -> str:
    parts = [
        f"Widerspruch {pack.adresse} Bescheid {bescheid_datum}".strip(),
        (req_text or "").strip()[:600],
    ]
    if pack.query_anchors:
        parts.append(" ".join(pack.query_anchors))
    if pack.laws_hint:
        parts.append(" ".join(pack.laws_hint))
    return " ".join(p for p in parts if p)