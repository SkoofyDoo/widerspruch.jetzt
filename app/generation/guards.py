"""Post-generation safety guards: style, strong claims, topic hallucinations."""
#TODO: 
from __future__ import annotations

import re
from typing import Any, Dict, List

from app.config import ANTRAEGE_WHITELIST
from app.utils import normalize_citation_order

ANTRAEGE_BANNED_TERMS_RX = re.compile(
    r"\b(heilung|wiedereinsetzung|nichtig|nichtigkeit|ungültig|unwirksam|offensichtlich|schwerwiegend)\b",
    re.IGNORECASE,
)

_WORK_TERMS_RX = re.compile(
    r"\b(Arbeit(?:geber|sstelle)?|Job|Beschäftigung|Tätigkeit|Arbeitsstelle|Arbeitsverhältnis)\b",
    re.IGNORECASE,
)
_TERMIN_TERMS_RX = re.compile(
    r"\b(Termin|Meldeversäumnis|Meldeaufforderung|Einladung)\b",
    re.IGNORECASE,
)
_KRANK_TERMS_RX = re.compile(
    r"\b(krank|Krankheit|Attest|ärztlich|Arbeitsunfähigkeit|AU)\b",
    re.IGNORECASE,
)
_ANHOERUNG_RX = re.compile(r"\b(Anhörung|§\s*24\s*SGB\s*X)\b", re.IGNORECASE)
_MINDERUNG_RX = re.compile(
    r"\b(kürzung|minderung|leistung(en)?\s*um|%|prozent|terminversäumnis|meldeversäumnis)\b",
    re.IGNORECASE,
)

_STYLE_FORBIDDEN_HEADINGS_RX = re.compile(
    r"^\s*(KURZER\s+SACHVERHALT|SACHVERHALT|RECHTLICHE\s+PUNKTE|RECHTLICHE\s+HINWEISE|ANTRÄGE|ANTRAG|BEGRÜNDUNG)\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_STYLE_FORBIDDEN_ENUM_RX = re.compile(r"^\s*[A-Z]\)\s+.*$", re.MULTILINE)
_STYLE_FORBIDDEN_BULLET_RX = re.compile(r"^\s*[-•]\s+.*$", re.MULTILINE)
_STYLE_FORBIDDEN_ANLAGEN_RX = re.compile(r"^\s*Anlagen\s*:.*$", re.IGNORECASE)
_STYLE_FORBIDDEN_ANLAGEN_ITEM_RX = re.compile(
    r"^\s*(?:-|\u2022)?\s*Kopie\s+(?:des|vom)\s+Bescheid", re.IGNORECASE
)

_BITTE_START_RX = re.compile(
    r"^\s*(Ich bitte(?: Sie)? um|Bitte bestätigen Sie|Ich bitte Sie um)\b", re.IGNORECASE
)
_BITTE_CONTAINS_RX = re.compile(
    r"\b(Eingangsbestätigung|Akteneinsicht|Erläuterung|Begründung|erneute Entscheidung|Überprüfung|Aufhebung|Neuberechnung)\b",
    re.IGNORECASE,
)
_BITTE_SOFT_RX = re.compile(
    r"^\s*(?:Bitte\s+prüfen\s+Sie\b|Ich\s+bitte\s+Sie\s+(?:daher|darum),\s*(?:den\s+Vorgang|den\s+Bescheid).{0,120}\bzu\s+prüfen\b)",
    re.IGNORECASE | re.DOTALL,
)

_STRONG_PATTERNS = [
    (re.compile(r"\bführt\s+zu[r]?\s+Nichtigkeit\b", re.IGNORECASE), "absolute_nichtigkeit"),
    (re.compile(r"\bist\s+rechtswidrig\b", re.IGNORECASE), "absolute_rechtswidrig"),
    (re.compile(r"\bkeine\s+Ausnahmen\s+vorliegen\b", re.IGNORECASE), "assumes_no_exceptions"),
    (re.compile(r"\bungültig\b|\bunwirksam\b", re.IGNORECASE), "invalidity_words"),
    (re.compile(r"\bnichtig(?:keit)?\b", re.IGNORECASE), "nichtigkeit_any"),
    (re.compile(r"\bschwerwiegenden?\s+Fehler\b", re.IGNORECASE), "schwerwiegender_fehler"),
    (re.compile(r"\bbesonders\s+schwerwiegenden?\s+Fehler\b", re.IGNORECASE), "besondere_schwere"),
    (re.compile(r"\bschwerwiegend\w*\b", re.IGNORECASE), "schwerwiegend_any"),
    (re.compile(r"\boffensichtlich\b", re.IGNORECASE), "offensichtlich_word"),
    (re.compile(r"\bohne\s+Zweifel\b|\beindeutig\b|\bsicher\b", re.IGNORECASE), "certainty_words"),
    (re.compile(r"\bes\s+ist\s+klar\b", re.IGNORECASE), "it_is_clear"),
    (re.compile(r"\bfragwürdig\b", re.IGNORECASE), "fragwuerdig"),
    (re.compile(r"\bwahrscheinlich\b", re.IGNORECASE), "wahrscheinlich"),
]


def sanitize_widerspruch_text(t: str) -> str:
    """Normalize phrasing, citations, and whitespace in generated text."""
    if not t:
        return ""
    t = re.sub(r"^\s*#{1,6}\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"\bwiderruf\b", "Widerspruch", t, flags=re.IGNORECASE)
    t = re.sub(r"\bwiderrufen\b", "Widerspruch einlegen", t, flags=re.IGNORECASE)
    t = re.sub(r"(§\s*31a)\s*SGB\s*X\b", r"\1 SGB II", t, flags=re.IGNORECASE)
    t = normalize_citation_order(t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)

    t = re.sub(r"\bWiderrufsprozesse?\b", "Verfahrensabläufe", t, flags=re.IGNORECASE)
    t = re.sub(r"\bWiderrufsprozess(?:e)?\b", "Verfahrensablauf", t, flags=re.IGNORECASE)
    t = re.sub(r"\bKopie des Bescheid\b", "Kopie des Bescheids", t, flags=re.IGNORECASE)
    t = re.sub(r"\bKopie vom Bescheid\b", "Kopie des Bescheids", t, flags=re.IGNORECASE)

    t = re.sub(r"\beinen\s+ärztlichen\s+Bescheinigung\b", "eine ärztliche Bescheinigung", t, flags=re.IGNORECASE)
    t = re.sub(r"\bärztlichen\s+Bescheinigung\b", "ärztliche Bescheinigung", t, flags=re.IGNORECASE)
    t = re.sub(r"\bKrankheitstellung\b", "Erkrankung", t, flags=re.IGNORECASE)
    t = re.sub(r"\bmeine\s+Arbeit\s+zu\s+versehen\b", "den Termin wahrzunehmen", t, flags=re.IGNORECASE)
    t = re.sub(r"\barbeit\s+zu\s+versehen\b", "den Termin wahrzunehmen", t, flags=re.IGNORECASE)
    t = re.sub(r"\brelevante\s+Zeitperiode\b", "den betreffenden Zeitraum", t, flags=re.IGNORECASE)

    return t.strip()


def remove_klaeger_terms(text: str) -> str:
    t = text or ""
    t = re.sub(r"\bDer\s+Kläger\b", "Ich", t, flags=re.IGNORECASE)
    t = re.sub(r"\bKläger\b", "Widerspruchsführer", t, flags=re.IGNORECASE)
    return t


def is_krank_attest_termin_case(req_text: str) -> bool:
    rt = req_text or ""
    return bool(_TERMIN_TERMS_RX.search(rt)) and bool(_KRANK_TERMS_RX.search(rt)) and bool(_MINDERUNG_RX.search(rt))


def user_explicitly_mentions_anhoerung(req_text: str) -> bool:
    rt = req_text or ""
    return bool(re.search(r"\banhörung\b|§\s*24\b", rt, flags=re.IGNORECASE))


def guard_remove_work_context_if_not_in_user_text(letter: str, req_text: str) -> str:
    lt = letter or ""
    ut = req_text or ""
    user_mentions_work = bool(_WORK_TERMS_RX.search(ut))
    user_mentions_termin = bool(_TERMIN_TERMS_RX.search(ut)) or ("termin" in ut.lower())
    user_mentions_km = bool(_KRANK_TERMS_RX.search(ut))

    if user_mentions_termin and user_mentions_km and (not user_mentions_work):
        lt = re.sub(r"\bmeine\s+Arbeit\s+zu\s+versehen\b", "den Termin wahrzunehmen", lt, flags=re.IGNORECASE)
        lt = re.sub(r"\bmeiner\s+Arbeit\b", "dem Termin", lt, flags=re.IGNORECASE)
        lt = re.sub(r"\bArbeitsstelle\b|\bArbeitgeber\b|\bArbeitsverhältnis\b", "", lt, flags=re.IGNORECASE)
        lt = re.sub(r"[ \t]{2,}", " ", lt)
        lt = re.sub(r"\n{3,}", "\n\n", lt)
        lt = lt.strip()
    return lt


def guard_remove_anhoerung_para_for_krank_attest(letter: str, req_text: str) -> str:
    """Drop §24 Anhörung boilerplate for sick-note appointment cases unless user asked."""
    if not is_krank_attest_termin_case(req_text):
        return letter
    if user_explicitly_mentions_anhoerung(req_text):
        return letter

    t = (letter or "").replace("\r\n", "\n").replace("\r", "\n")
    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    if not paras:
        return letter

    removed = False
    new_paras = []
    for p in paras:
        if _ANHOERUNG_RX.search(p):
            if "Sehr geehrte" in p or "Betreff:" in p or "Mit freundlichen Grüßen" in p:
                new_paras.append(p)
            else:
                removed = True
            continue
        new_paras.append(p)

    if removed:
        joined = "\n\n".join(new_paras)
        if not re.search(r"\bwichtiger\s+Grund\b", joined, flags=re.IGNORECASE):
            insert_text = (
                "Ich bitte um Prüfung des Vorgangs unter Berücksichtigung meiner Erkrankung als wichtiger Grund "
                "sowie um eine entsprechende Neubewertung."
            )
            inserted = False
            out2 = []
            for p in new_paras:
                if (not inserted) and re.match(r"^Ich bitte\b", p, flags=re.IGNORECASE):
                    out2.append(insert_text)
                    inserted = True
                out2.append(p)
            new_paras = out2 if inserted else (new_paras + [insert_text])

        t2 = "\n\n".join(new_paras)
        return sanitize_widerspruch_text(t2)

    return letter


def flatten_list_block(lines: List[str]) -> str:
    items = []
    for ln in lines:
        ln = re.sub(r"^\s*[-•]\s+", "", ln).strip()
        ln = re.sub(r"\s*;\s*$", "", ln).strip()
        if ln:
            items.append(ln)
    if not items:
        return ""
    s = "; ".join(items)
    if not s.endswith("."):
        s += "."
    return s


def enforce_official_no_lists(body: str) -> str:
    """Convert bullet/enum style into continuous official-letter paragraphs."""
    t = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    t = remove_klaeger_terms(t)

    t = "\n".join([ln for ln in t.split("\n") if not _STYLE_FORBIDDEN_ANLAGEN_RX.match(ln)])
    t = "\n".join([ln for ln in t.split("\n") if not _STYLE_FORBIDDEN_ANLAGEN_ITEM_RX.match(ln)])
    t = _STYLE_FORBIDDEN_HEADINGS_RX.sub("", t)
    t = _STYLE_FORBIDDEN_ENUM_RX.sub("", t)

    out_lines = []
    buf_bullets = []
    for raw in t.split("\n"):
        ln = raw.rstrip()
        if _STYLE_FORBIDDEN_BULLET_RX.match(ln):
            buf_bullets.append(ln)
            continue
        if buf_bullets:
            flat = flatten_list_block(buf_bullets)
            if flat:
                out_lines.append(flat)
            buf_bullets = []
        out_lines.append(ln)
    if buf_bullets:
        flat = flatten_list_block(buf_bullets)
        if flat:
            out_lines.append(flat)

    t2 = "\n".join(out_lines)
    t2 = re.sub(r"\n{3,}", "\n\n", t2).strip()
    if not t2.strip():
        t2 = "Ich bitte um Prüfung des Bescheids und um eine erneute Entscheidung."
    return t2


def build_safe_bitte_paragraph(req_text: str) -> str:
    rt = req_text or ""
    wants_akte = bool(re.search(r"\bakteneinsicht\b", rt, flags=re.IGNORECASE))
    wants_begruendung = bool(re.search(r"\bbegründung\b|\berläuterung\b|\bnachvollziehbar\b", rt, flags=re.IGNORECASE))
    wants_minderung_aufhebung = bool(_MINDERUNG_RX.search(rt))

    parts = [ANTRAEGE_WHITELIST[0]]
    if wants_akte:
        parts.append(ANTRAEGE_WHITELIST[1])
    if wants_begruendung:
        parts.append(ANTRAEGE_WHITELIST[2])
    parts.append(ANTRAEGE_WHITELIST[3])
    if wants_minderung_aufhebung:
        parts.append(ANTRAEGE_WHITELIST[4])
    return "Ich bitte um " + "; ".join(parts) + "."


def dedupe_and_fix_bitte_paragraphs(head_text: str, req_text: str) -> str:
    t = (head_text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = remove_klaeger_terms(t)
    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    if not paras:
        return build_safe_bitte_paragraph(req_text)

    found_idx = []
    for i, p in enumerate(paras):
        if _BITTE_START_RX.search(p) or _BITTE_SOFT_RX.search(p) or (
            _BITTE_CONTAINS_RX.search(p) and "Mit freundlichen Grüßen" not in p
        ):
            found_idx.append(i)

    if not found_idx:
        paras.append(build_safe_bitte_paragraph(req_text))
        return "\n\n".join(paras).strip()

    keep = found_idx[-1]
    new_paras = []
    for i, p in enumerate(paras):
        if i in found_idx and i != keep:
            continue
        new_paras.append(p)

    kept_para = paras[keep]
    keep_new = 0
    for i, p in enumerate(new_paras):
        if p == kept_para:
            keep_new = i
            break

    kept = new_paras[keep_new]
    if ANTRAEGE_BANNED_TERMS_RX.search(kept) or len(kept) > 520:
        new_paras[keep_new] = build_safe_bitte_paragraph(req_text)
    if not re.search(r"\bEingangsbestätigung\b", new_paras[keep_new], flags=re.IGNORECASE):
        new_paras[keep_new] = build_safe_bitte_paragraph(req_text)
    if bool(_MINDERUNG_RX.search(req_text or "")):
        if not re.search(r"\bAufhebung\b|\bNeuberechnung\b", new_paras[keep_new], flags=re.IGNORECASE):
            new_paras[keep_new] = build_safe_bitte_paragraph(req_text)

    kept_now = new_paras[keep_new]
    if _BITTE_START_RX.search(kept_now):
        cleaned = []
        for idx, p in enumerate(new_paras):
            if idx != keep_new and _BITTE_SOFT_RX.search(p):
                continue
            cleaned.append(p)
        new_paras = cleaned

    return "\n\n".join(new_paras).strip()


def find_strong_claims(text: str) -> List[str]:
    t = normalize_citation_order(text or "")
    hits = []
    for rx, name in _STRONG_PATTERNS:
        if rx.search(t):
            hits.append(name)
    return hits


def hard_soften_strong_claims(text: str) -> str:
    t = normalize_citation_order(text or "")
    ban_replacements = {
        r"\bführt\s+zu[r]?\s+Nichtigkeit\b": "kann einen Verfahrensmangel begründen",
        r"\bist\s+rechtswidrig\b": "erscheint rechtswidrig",
        r"\bkeine\s+Ausnahmen\s+vorliegen\b": "soweit keine Ausnahme eingreift",
        r"\bungültig\b|\bunwirksam\b": "verfahrensfehlerhaft",
        r"\bnichtig(?:keit)?\b": "Verfahrensmangel",
        r"\bschwerwiegenden?\s+Fehler\b": "Verfahrensmangel",
        r"\bbesonders\s+schwerwiegenden?\s+Fehler\b": "Verfahrensmangel",
        r"\bschwerwiegend\w*\b": "",
        r"\boffensichtlich\b": "",
        r"\bohne\s+Zweifel\b|\beindeutig\b|\bsicher\b": "nach Aktenlage",
        r"\bes\s+ist\s+klar\b": "nach Aktenlage",
        r"\bfragwürdig\b": "prüfungsbedürftig",
        r"\bwahrscheinlich\b": "",
    }
    for pat, repl in ban_replacements.items():
        t = re.sub(pat, repl, t, flags=re.IGNORECASE)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def validate_text(text: str) -> Dict[str, Any]:
    t = (text or "").strip()
    warnings, errors = [], []

    if not re.search(r"Sehr geehrte Damen und Herren", t, flags=re.IGNORECASE):
        errors.append("Missing standard greeting 'Sehr geehrte Damen und Herren,'.")
    if re.search(r"\bWiderruf\b|\bwiderrufen\b|\bwiderrufe\b", t, flags=re.IGNORECASE):
        errors.append("Contains Widerruf/Widerrufen. Must be Widerspruch (not Widerruf).")
    if re.search(r"\bWiderspruch\b", t, flags=re.IGNORECASE) is None:
        errors.append("Missing keyword 'Widerspruch' in the letter text.")
    if re.search(r"\bKläger\b", t, flags=re.IGNORECASE):
        warnings.append("Contains 'Kläger' — should be avoided in Widerspruch (court term).")
    if _STYLE_FORBIDDEN_BULLET_RX.search(t):
        warnings.append("Contains bullet list lines — should be paragraphs for official letter style.")
    if _STYLE_FORBIDDEN_ENUM_RX.search(t):
        warnings.append("Contains A)/B) style enumerations — should be avoided.")

    ok = len(errors) == 0
    return {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "counts": {"errors": len(errors), "warnings": len(warnings)},
    }
