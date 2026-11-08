from __future__ import annotations

from dataclasses import dataclass, field

@dataclass(frozen=True)
class DomainPack:
    id: str
    label: str
    adresse: str
    query_anchors: tuple[str, ...] = ()
    laws_hint: tuple[str, ...] = ()
    extra_rules: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    
DOMAINS: dict[str, DomainPack] = {
    "jobcenter_minderung": DomainPack(
        id="jobcenter_minderung",
        label="Jobcenter / Minderung / Sanktion",
        adresse="Jobcenter",
        query_anchors=("Minderung", "Sanktion", "Zumutbarkeit", "Pflichtverletzung"),
        laws_hint=("SGB II", "SGB X", "SGG"),
        extra_rules=(
            "Fokus auf Leistungsminderung/Sanktion und Zumutbarkeit.",
            "Keine KdU-/Miet-Argumente, sofern USER_TEXT das nicht nennt.",
        ),
        keywords=(
            "minderung",
            "sanktion",
            "pflichtverletzung",
            "unzumutbar",
            "zumutbar",
        ),
    ),
    "jobcenter_kdu": DomainPack(
        id="jobcenter_kdu",
        label="Jobcenter / Kosten der Unterkunft",
        adresse="Jobcenter",
        query_anchors=("Kosten der Unterkunft", "Heizung", "Angemessenheit", "Zusicherung"),
        laws_hint=("SGB II", "SGB X"),
        extra_rules=(
            "Fokus auf Unterkunft und Heizung.",
            "Keine Sanktions-Argumente, sofern USER_TEXT das nicht nennt.",
        ),
        keywords=("unterkunft", "heizung", "miete", "kdu", "wohnkosten", "umzug"),
    ),
    "jobcenter_termin": DomainPack(
        id="jobcenter_termin",
        label="Jobcenter / Termin / Meldeversäumnis",
        adresse="Jobcenter",
        query_anchors=("Meldeaufforderung", "Termin", "Meldeversäumnis"),
        laws_hint=("SGB II", "SGB X"),
        extra_rules=(
            "Nur terminbezogene Formulierungen.",
            "Nicht von Arbeit/Arbeitgeber sprechen, wenn USER_TEXT das nicht nennt.",
        ),
        keywords=("termin", "meldeversäumnis", "meldeaufforderung", "erscheinungs"),
    ),
    "jobcenter_general": DomainPack(
        id="jobcenter_general",
        label="Jobcenter / allgemein",
        adresse="Jobcenter",
        query_anchors=("Widerspruch", "Bescheid", "Bürgergeld"),
        laws_hint=("SGB II", "SGB X", "SGG"),
        extra_rules=("Allgemeiner Widerspruch gegen einen Jobcenter-Bescheid.",),
        keywords=("jobcenter", "bürgergeld", "alg ii", "sgb ii", "leistung"),
    ),
    "generic": DomainPack(
        id="generic",
        label="Allgemeiner Behördenwiderspruch",
        adresse="zuständige Behörde",
        query_anchors=("Widerspruch", "Bescheid", "Verwaltungsakt"),
        laws_hint=(),
        extra_rules=(
            "Kein Jobcenter-spezifischer Jargon, sofern USER_TEXT das nicht hergibt.",
        ),
        keywords=(),
    ),
}


def get_pack(domain_id: str) -> DomainPack:
    return DOMAINS.get(domain_id) or DOMAINS["generic"]