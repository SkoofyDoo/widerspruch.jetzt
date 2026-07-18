"""LLM prompts for body generation, polish, and repair passes."""

from __future__ import annotations

from typing import List

from app.generation.llm import call_llm
from app.rag.citations import allowed_citations_from_items
from app.utils import safe_str


def widerspruch_body_prompt(context: str, facts: dict, req_text: str) -> str:
    bescheid_datum = safe_str(facts.get("bescheid_datum"))
    zugang_datum = safe_str(facts.get("zugang_datum"))

    return f"""SYSTEM:
Du schreibst den INHALT (Fließtext) eines formellen deutschen Widerspruchs an ein Jobcenter.

HARTE REGELN:
- Schreibe ausschließlich in zusammenhängenden Absätzen (Fließtext). KEINE Überschriften, KEINE Listen, KEINE Aufzählungszeichen, KEINE A)/B).
- Verwende NICHT die Begriffe "Kläger", "Beklagter".
- Verwende NUR Fakten aus USER_TEXT und FACTS. Keine erfundenen Details.
- Zitiere Gesetze (§) NUR, wenn sie im CONTEXT stehen. Sonst keine §-Nummern.
- KEINE starken Schlussfolgerungen: NICHT "ungültig", "unwirksam", "nichtig", "Nichtigkeit", "offensichtlich", "schwerwiegend".
- Keine Garantien. Nur neutral: "bitte prüfen", "es bestehen Zweifel", "nach Aktenlage".
- WICHTIG: Erst 1–3 Absätze zur kurzen Begründung/Prüfbitte, DANACH als letzten Absatz eine kurze Bitte (Eingangsbestätigung / ggf. Akteneinsicht / ggf. Erläuterung / erneute Entscheidung).
- Schreibe KEINEN Abschnitt "Anlagen" und erwähne "Anlagen" nicht. Anlagen werden außerhalb des Bodys eingefügt.

TOPIC GUARDS:
- Wenn USER_TEXT von "Termin" / "Meldeversäumnis" handelt: Verwende ausschließlich Termin-bezogene Formulierungen (z.B. "den Termin wahrnehmen") und NICHT "Arbeit/Job/Arbeitgeber".
- Wenn USER_TEXT "krank" + "Attest/Bescheinigung" enthält: Nenne diese Fakten kurz ("krankheitsbedingt", "ärztliche Bescheinigung liegt vor", "nicht rechtzeitig eingereicht") ohne zusätzliche erfundene Hintergründe.
- WICHTIG: In Krank+Attest+Termin-Fällen keine Standard-Passagen zur "Anhörung" oder "§ 24 SGB X" verwenden, es sei denn USER_TEXT nennt ausdrücklich "Anhörung" oder "§ 24".

FORMAT:
- 3 bis 6 Absätze, jeweils 2–4 Sätze.
- Keine Überschriften, keine Bulletpoints.

FACTS:
Bescheid-Datum: {bescheid_datum}
Zugang-Datum: {zugang_datum}

USER_TEXT:
{(req_text or "").strip()}

CONTEXT:
{(context or "").strip()}

Gib ausschließlich den Text zurück.
"""


def polish_with_ollama(base_letter: str, style: str) -> str:
    style = (style or "standard").lower().strip()
    if style == "short":
        style_hint = "Halte die Formulierungen knapp, aber ändere keine Struktur."
    elif style == "formal":
        style_hint = "Sehr formell und neutral, aber ändere keine Struktur."
    else:
        style_hint = "Neutral und gut lesbar, aber ändere keine Struktur."
    prompt = f"""SYSTEM:
Du bist ein reiner Korrektur- und Stilassistent.
WICHTIG:
- Du darfst KEINE neuen Fakten hinzufügen.
- Du darfst KEINE neuen Abschnitte hinzufügen.
- Du darfst KEINE Abschnitte entfernen.
- Du darfst KEINE neuen Gesetzesverweise hinzufügen.
- Keine Überschriften, keine Listen, keine A)/B).
- Gib ausschließlich den korrigierten Text zurück, ohne Kommentare.

STYLE:
{style_hint}

TEXT:
{base_letter}
"""
    out = call_llm(prompt)
    return out.strip() if out else base_letter


def repair_illegal_citations_with_ollama(text: str, items, illegal: List[str]) -> str:
    allowed = sorted(list(allowed_citations_from_items(items)))
    prompt = f"""SYSTEM:
Du bist ein strenger Korrektur-Assistent für einen Widerspruch ans Jobcenter.
WICHTIG:
- Entferne/ersetze ALLE unzulässigen Gesetzesverweise, die NICHT in ALLOWED_CITATIONS stehen.
- Du darfst KEINE neuen §-Zitate hinzufügen.
- Du darfst KEINE neuen Fakten hinzufügen.
- Gib nur den korrigierten Brieftext zurück, ohne Kommentare.

ALLOWED_CITATIONS:
{", ".join(allowed) if allowed else "(keine)"}

ILLEGAL_FOUND:
{", ".join(illegal)}

TEXT_TO_FIX:
{text}
"""
    out = call_llm(prompt).strip()
    return out if out else text


def repair_strong_claims_with_ollama(text: str, flags: List[str]) -> str:
    prompt = f"""SYSTEM:
Du bist ein strenger Korrektur-Assistent für einen Widerspruch ans Jobcenter.
WICHTIG:
- Entferne oder entschärfe ALLE zu starken/absoluten rechtlichen Schlussfolgerungen.
- Keine Formulierungen wie: "ungültig", "unwirksam", "nichtig", "Nichtigkeit", "offensichtlich", "schwerwiegend".
- Keine absoluten Aussagen / keine Erfolgsgarantien.
- Ersetze durch vorsichtige Formulierungen: "bitte prüfen", "nach Aktenlage", "es bestehen Zweifel".
- Du darfst KEINE neuen Fakten hinzufügen.
- Du darfst KEINE neuen Gesetzesverweise hinzufügen.
- Gib nur den korrigierten Brieftext zurück, ohne Kommentare.

STRONG_FLAGS:
{", ".join(flags)}

TEXT_TO_FIX:
{text}
"""
    out = call_llm(prompt).strip()
    return out if out else text
