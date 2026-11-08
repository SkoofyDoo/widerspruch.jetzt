"""LLM prompts for body generation, polish, and repair passes."""

from __future__ import annotations

from typing import List

from app.generation.llm import call_llm
from app.rag.v1.citations import allowed_citations_from_items
from app.utils import safe_str

def format_allow_list(items) -> str:
    """Humanreadable Whitelist aus den RAG-Hits"""
    lines = []
    seen = set()
    for it in items or []:
        law = (it.get("law") or "").strip()
        paragraph = (it.get("paragraph") or "").strip()
        absatz = (it.get("absatz") or "").strip()
        if not law or not paragraph:
            continue
        key = f"{law}::{paragraph}"
        if key in seen:
            continue
        seen.add(key)
        bit = f"{absatz}" if absatz else ""
        lines.append(f"- {law} {paragraph}{bit}")
    return "\n".join(lines) if lines else ""




def widerspruch_body_prompt(context: str, facts: dict, req_text: str, items=None, pack=None) -> str:

    bescheid_datum = safe_str(facts.get("bescheid_datum"))
    zugang_datum = safe_str(facts.get("zugang_datum"))
    allowlist = format_allow_list(items)

    adresse = getattr(pack, "adresse", "zuständige Behörde") if pack else "zuständige Behörde"
    extra = ""
    if pack and pack.extra_rules:
        extra = "DOMAIN_RULES:\n" + "\n".join(f"- {r}" for r in pack.extra_rules)

    return f"""SYSTEM:
Du schreibst nur den MITTELTEIL eines deutschen Amtsbriefs (Widerspruch) an: {adresse}.
Anrede, Betreff, Bezugssatz und Grußformel sind schon gesetzt — wiederhole sie nicht.

FORM:
- Genau drei Absätze Fließtext, getrennt durch Leerzeile.
- Ich-Perspektive («ich», «mein»). Niemals «Antragsteller/in», «Kläger/in».
- Keine Nummern, keine Markdown (**fett**), keine Labels wie «Sachverhalt:» / «Prüfbitte:».
- Keine Stichpunkte, keine Analyse, kein «Denken laut».

INHALT der drei Absätze (ohne Überschriften):
Absatz A — kurz der Fall aus USER_TEXT/FACTS.
Absatz B — ein bis zwei knappe rechtliche Gedanken mit höchstens zwei kurzen §-Bezugnahmen
  aus ERLAUBTE_NORMEN (nur wenn passend). Kein Abschreiben des Gesetzestextes.
Absatz C — höfliche Prüfbitte (Eingangsbestätigung, Prüfung, neue Entscheidung).

VERBOTEN:
- fremde Themen, die USER_TEXT nicht nennt
- wörtliche Gesetzeswiedergabe aus CONTEXT
- starke Worte: ungültig, unwirksam, nichtig, offensichtlich, schwerwiegend
- Widersprüche oder Spekulation («weil kein Attest, deshalb ungerechtfertigt» ohne Beleg im USER_TEXT)

BEISPIEL GUT:
Zum angegebenen Termin konnte ich krankheitsbedingt nicht erscheinen; eine ärztliche Bescheinigung liegt vor.

Nach Aktenlage bestehen Zweifel, ob die Leistungsminderung unter Berücksichtigung dieses wichtigen Grundes zutreffend ist; insoweit wird auf § 31a SGB II Bezug genommen.

Ich bitte um Eingangsbestätigung, erneute Prüfung und eine neue Entscheidung.

BEISPIEL SCHLECHT (so niemals schreiben):
1. **Sachverhalt**: Die Antragstellerin …
2. **Rechtliche Würdigung**: … langer Gesetzestext …
{extra}

ERLAUBTE_NORMEN (höchstens 2 passende nutzen):
{allowlist}

FACTS:
Bescheid-Datum: {bescheid_datum}
Zugang-Datum: {zugang_datum}

USER_TEXT:
{(req_text or "").strip()}

CONTEXT (nur Hintergrund, nicht abschreiben):
{(context or "").strip()}

Gib nur die drei Absätze Fließtext zurück.
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
