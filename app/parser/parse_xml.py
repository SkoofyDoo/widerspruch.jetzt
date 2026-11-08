"""Parse GII XML norms → data/norms.jsonl (+ cleaned/*.txt for legacy ingest)."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_XML_DIR = ROOT / "data" / "raw_xml"
NORMS_JSONL = ROOT / "data" / "norms.jsonl"
CLEANED_DIR = ROOT / "data" / "cleaned"

ABSATZ_RE = re.compile(r"^\((\d+[a-z]?)\)\s*")
WS_RE = re.compile(r"\s+")

# jurabk from GII → (display law, file prefix)
LAW_NORMALIZE = {
    "SGB 2": ("SGB II", "sgb2"),
    "SGB2": ("SGB II", "sgb2"),
    "SGB II": ("SGB II", "sgb2"),
    "SGB 10": ("SGB X", "sgbx"),
    "SGB10": ("SGB X", "sgbx"),
    "SGB X": ("SGB X", "sgbx"),
    "SGG": ("SGG", "sgg"),
}


@dataclass
class Absatz:
    label: str  # "(1)", "(2a)", or ""
    text: str


@dataclass
class Norm:
    law: str
    law_key: str
    paragraph: str
    title: str
    source_xml: str
    absätze: list[Absatz]

    def full_text(self) -> str:
        header = f"{self.paragraph} {self.title}".strip()
        body = "\n".join(
            f"{a.label} {a.text}".strip() if a.label else a.text for a in self.absätze
        )
        return f"{header}\n{body}".strip() if body else header


def normalize_law(jurabk: str) -> tuple[str, str]:
    key = (jurabk or "").strip()
    if key in LAW_NORMALIZE:
        return LAW_NORMALIZE[key]
    compact = key.upper().replace(" ", "")
    for raw, mapped in LAW_NORMALIZE.items():
        if raw.upper().replace(" ", "") == compact:
            return mapped
    return (key or "UNKNOWN", "other")


def normalize_paragraph(enbez: str) -> str | None:
    """Return '§ 1' / '§ 3a' or None if this norm is not a paragraph."""
    enbez = (enbez or "").strip()
    m = re.match(r"^§\s*(\d+)([a-zA-Z]?)\s*$", enbez, re.I)
    if not m:
        return None
    return f"§ {m.group(1)}{m.group(2).lower()}"


def element_text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    parts = [t.strip() for t in el.itertext() if t and t.strip()]
    return WS_RE.sub(" ", " ".join(parts)).strip()


def split_absatz(text: str) -> Absatz:
    m = ABSATZ_RE.match(text)
    if not m:
        return Absatz(label="", text=text)
    return Absatz(label=f"({m.group(1)})", text=text[m.end() :].strip())


def parse_norm(norm_el: ET.Element, source_xml: str) -> Norm | None:
    meta = norm_el.find("metadaten")
    if meta is None:
        return None

    paragraph = normalize_paragraph(meta.findtext("enbez") or "")
    if not paragraph:
        return None

    law, law_key = normalize_law(meta.findtext("jurabk") or "")
    title = (meta.findtext("titel") or "").strip()

    absätze: list[Absatz] = []
    for p in norm_el.findall(".//textdaten/text/Content/P"):
        raw = element_text(p)
        if not raw:
            continue
        absätze.append(split_absatz(raw))

    # Fallback: any P under textdaten (older / odd layouts)
    if not absätze:
        for p in norm_el.findall(".//textdaten//P"):
            raw = element_text(p)
            if not raw:
                continue
            absätze.append(split_absatz(raw))

    if not absätze:
        return None

    return Norm(
        law=law,
        law_key=law_key,
        paragraph=paragraph,
        title=title,
        source_xml=source_xml,
        absätze=absätze,
    )


def iter_xml_files(raw_dir: Path) -> list[Path]:
    if not raw_dir.is_dir():
        return []
    return sorted(raw_dir.rglob("*.xml"))


def parse_xml_file(path: Path) -> list[Norm]:
    root = ET.parse(path).getroot()
    norms: list[Norm] = []
    for norm_el in root.findall("norm"):
        parsed = parse_norm(norm_el, source_xml=path.name)
        if parsed is not None:
            norms.append(parsed)
    return norms


def paragraph_slug(paragraph: str) -> str:
    m = re.search(r"(\d+[a-z]?)", paragraph, re.I)
    return (m.group(1).lower() if m else "unknown")


def _set_chroma_rebuild(needed: bool) -> None:
    from app.rag.v2.rebuild_flag import write_rebuild_flag

    write_rebuild_flag(needed)


def _paragraph_key(law_key: str, paragraph: str) -> str:
    return f"{law_key}::{paragraph}"


def _load_previous_paragraph_map(path: Path) -> dict[str, str]:
    """Map law_key::paragraph → full text (for change detection)."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            key = _paragraph_key(row.get("law_key") or "", row.get("paragraph") or "")
            out[key] = row.get("text") or ""
    return out


def detect_corpus_changes(
    norms: list[Norm], previous: dict[str, str]
) -> tuple[bool, list[str]]:
    """True when paragraphs were added, removed, or their text changed."""
    current: dict[str, str] = {
        _paragraph_key(n.law_key, n.paragraph): n.full_text() for n in norms
    }
    if not previous:
        return True, [f"initial corpus ({len(current)} paragraphs)"]

    reasons: list[str] = []
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    changed = sorted(
        k for k in set(current) & set(previous) if current[k] != previous[k]
    )
    if added:
        reasons.append(f"added {len(added)}: {', '.join(added[:8])}" + ("…" if len(added) > 8 else ""))
    if removed:
        reasons.append(
            f"removed {len(removed)}: {', '.join(removed[:8])}"
            + ("…" if len(removed) > 8 else "")
        )
    if changed:
        reasons.append(
            f"changed text {len(changed)}: {', '.join(changed[:8])}"
            + ("…" if len(changed) > 8 else "")
        )
    return bool(reasons), reasons


def write_outputs(norms: list[Norm], write_cleaned: bool = True) -> None:
    previous = _load_previous_paragraph_map(NORMS_JSONL)
    needs_rebuild, reasons = detect_corpus_changes(norms, previous)
    if needs_rebuild:
        for reason in reasons:
            print(f"[CORPUS CHANGE]: {reason}")
        _set_chroma_rebuild(True)
    else:
        print("[CORPUS CHANGE]: none — rebuild flag left unchanged")

    NORMS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with NORMS_JSONL.open("w", encoding="utf-8") as f:
        for norm in norms:
            row = {
                "law": norm.law,
                "law_key": norm.law_key,
                "paragraph": norm.paragraph,
                "title": norm.title,
                "source_xml": norm.source_xml,
                "source_file": f"{norm.law_key}__{paragraph_slug(norm.paragraph)}.txt",
                "absätze": [asdict(a) for a in norm.absätze],
                "text": norm.full_text(),
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(norms)} norms -> {NORMS_JSONL}")

    if not write_cleaned:
        return

    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    # Remove previous XML-derived cleaned files we own (prefix sgb2__/sgbx__/sgg__)
    for pattern in ("sgb2__*.txt", "sgbx__*.txt", "sgg__*.txt"):
        for old in CLEANED_DIR.glob(pattern):
            old.unlink()

    for norm in norms:
        out = CLEANED_DIR / f"{norm.law_key}__{paragraph_slug(norm.paragraph)}.txt"
        out.write_text(norm.full_text() + "\n", encoding="utf-8")
    print(f"Wrote {len(norms)} cleaned txt -> {CLEANED_DIR}")


def main() -> None:
    xml_files = iter_xml_files(RAW_XML_DIR)
    if not xml_files:
        raise RuntimeError(
            f"No XML under {RAW_XML_DIR}. Run: python -m app.parser.fetch_xml"
        )

    norms: list[Norm] = []
    for path in xml_files:
        found = parse_xml_file(path)
        print(f"[{path.parent.name}] {path.name}: {len(found)} paragraphs")
        norms.extend(found)

    if not norms:
        raise RuntimeError("Parsed 0 paragraph norms — check XML layout")

    # Stable order: law_key then paragraph number
    def sort_key(n: Norm) -> tuple:
        m = re.search(r"(\d+)([a-z]?)", n.paragraph, re.I)
        num = int(m.group(1)) if m else 0
        letter = m.group(2).lower() if m else ""
        return (n.law_key, num, letter)

    norms.sort(key=sort_key)
    write_outputs(norms, write_cleaned=True)

    by_law: dict[str, int] = {}
    for n in norms:
        by_law[n.law] = by_law.get(n.law, 0) + 1
    print("By law:", by_law)


if __name__ == "__main__":
    main()
