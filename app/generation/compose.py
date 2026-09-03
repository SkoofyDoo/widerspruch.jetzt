"""Deterministic letter header / Anlagen composition (not LLM-generated)."""

# TODO: Formattierung der Ausgabe mit der LLM 
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional

from app.generation.guards import remove_klaeger_terms, sanitize_widerspruch_text
from app.utils import fmt_bescheid_date_display, fmt_de_long, safe_str


def fmt_jobcenter_address(facts: Dict[str, Any]) -> Optional[str]:
    addr = safe_str(facts.get("jobcenter_address"))
    plz = safe_str(
        facts.get("jobcenter_postalCode") or facts.get("jobcenter_postal_code") or facts.get("jobcenter_plz")
    )
    city = safe_str(facts.get("jobcenter_city"))
    parts = []
    if addr:
        parts.append(addr)
    if plz or city:
        parts.append(" ".join([p for p in [plz, city] if p]).strip())
    out = "\n".join([p for p in parts if p])
    return out if out else None


def fmt_user_block(facts: Dict[str, Any]) -> str:
    lines = []
    name = " ".join([p for p in [safe_str(facts.get("vorname")), safe_str(facts.get("nachname"))] if p]).strip()
    if name:
        lines.append(name)

    kunden = safe_str(facts.get("kunden_nummer") or facts.get("bg_nummer"))
    if kunden:
        lines.append(f"BG/Kundennummer: {kunden}")

    addr = safe_str(facts.get("user_address"))
    plz = safe_str(facts.get("user_postalCode") or facts.get("user_postal_code") or facts.get("user_plz"))
    city = safe_str(facts.get("user_city"))

    if addr:
        lines.append(addr)
    if plz or (city and addr):
        line = " ".join([p for p in [plz, city] if p]).strip()
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def fmt_jobcenter_block_strict(facts: Dict[str, Any]) -> str:
    jc_label = safe_str(facts.get("jobcenter_label") or facts.get("jobcenter"))
    jc_addr = fmt_jobcenter_address(facts)
    if jc_label and jc_addr:
        return f"An\n{jc_label}\n{jc_addr}".strip()
    if jc_label:
        return f"An\n{jc_label}".strip()
    if jc_addr:
        return f"An\nJobcenter\n{jc_addr}".strip()
    return "An\ndas zuständige Jobcenter"


def fmt_date_line(facts: Dict[str, Any]) -> str:
    dt = safe_str(facts.get("letter_date"))
    if not dt:
        dt = fmt_de_long(date.today())
    user_city = safe_str(facts.get("user_city"))
    if user_city:
        return f"{user_city}, den {dt}"
    return dt


def make_anlagen_list(req_text: str, facts: Dict[str, Any]) -> List[str]:
    if bool(facts.get("no_anlagen")):
        return []
    out = ["Kopie des Bescheids"]
    extra = facts.get("anlagen")
    if isinstance(extra, list):
        for x in extra:
            s = safe_str(x)
            s = re.sub(r"[.]+$", "", s).strip()
            if s:
                out.append(s)

    seen, uniq = set(), []
    for a in out:
        a2 = re.sub(r"[.]+$", "", (a or "")).strip()
        if not a2:
            continue
        key = a2.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(a2)
    return uniq


def compose_letter_enforced_header(
    facts: Dict[str, Any], req_text: str, body: str, include_anlagen: bool = True
) -> str:
    user_block = fmt_user_block(facts)
    jc_block = fmt_jobcenter_block_strict(facts)
    date_line = fmt_date_line(facts)

    bescheid_raw = safe_str(facts.get("bescheid_datum"))
    bescheid_disp = fmt_bescheid_date_display(bescheid_raw) if bescheid_raw else ""
    subject = f"Betreff: Widerspruch gegen Bescheid vom {bescheid_disp}" if bescheid_disp else "Betreff: Widerspruch"
    name = " ".join([p for p in [safe_str(facts.get("vorname")), safe_str(facts.get("nachname"))] if p]).strip()

    parts = []
    if user_block:
        parts.append(user_block)
        parts.append("")
    parts.append(jc_block)
    parts.append("")
    parts.append(date_line)
    parts.append("")
    parts.append(subject)
    parts.append("")
    parts.append("Sehr geehrte Damen und Herren,")
    parts.append("")
    parts.append(f"hiermit lege ich Widerspruch gegen den Bescheid{(' vom ' + bescheid_disp) if bescheid_disp else ''} ein.")
    parts.append("")
    parts.append((body or "").strip())
    parts.append("")
    parts.append("Mit freundlichen Grüßen")
    if name:
        parts.append(name)

    if include_anlagen:
        anlagen = make_anlagen_list(req_text=req_text, facts=facts)
        if anlagen:
            parts.append("")
            parts.append("Anlagen:")
            for a in anlagen:
                aa = re.sub(r"[.]+$", "", (a or "")).strip()
                if aa:
                    parts.append(f"- {aa}")

    out = "\n".join(parts)
    out = sanitize_widerspruch_text(out)
    out = remove_klaeger_terms(out)
    return out.strip()
