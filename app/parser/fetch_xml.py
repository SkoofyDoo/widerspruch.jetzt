"""Download official GII XML ZIPs (SGB II / SGB X / SGG) into data/raw_xml/."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import TypedDict

import requests

HEADERS = {"User-Agent": "widerspruch.jetzt-corpus/1.0 (offline ingest; +https://widerspruch.jetzt)"}
ROOT = Path(__file__).resolve().parents[2]
RAW_XML_DIR = ROOT / "data" / "raw_xml"
TOC_URL = "https://www.gesetze-im-internet.de/gii-toc.xml"


class Source(TypedDict):
    name: str
    zip_url: str
    out: Path


# Stable direct ZIP URLs (official GII). TOC is used only as fallback.
SOURCES: list[Source] = [
    {
        "name": "sgb2",
        "zip_url": "https://www.gesetze-im-internet.de/sgb_2/xml.zip",
        "out": RAW_XML_DIR / "sgb2",
    },
    {
        "name": "sgbx",
        "zip_url": "https://www.gesetze-im-internet.de/sgb_10/xml.zip",
        "out": RAW_XML_DIR / "sgbx",
    },
    {
        "name": "sgg",
        "zip_url": "https://www.gesetze-im-internet.de/sgg/xml.zip",
        "out": RAW_XML_DIR / "sgg",
    },
]


def fetch_bytes(url: str) -> bytes:
    r = requests.get(url, headers=HEADERS, timeout=60)
    print("FETCH", r.status_code, "|", r.url)
    r.raise_for_status()
    return r.content


def extract_xml_zip(blob: bytes, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".xml"):
                continue
            target = out_dir / Path(name).name
            target.write_bytes(zf.read(name))
            written.append(target)
    return written


def fetch_source(source: Source) -> list[Path]:
    blob = fetch_bytes(source["zip_url"])
    paths = extract_xml_zip(blob, source["out"])
    if not paths:
        raise RuntimeError(f"No XML in zip for {source['name']}: {source['zip_url']}")
    for p in paths:
        print(f"[{source['name']}] saved -> {p} ({p.stat().st_size} bytes)")
    return paths


def main() -> None:
    RAW_XML_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for source in SOURCES:
        total += len(fetch_source(source))
    print(f"Done. XML files: {total} under {RAW_XML_DIR}")


if __name__ == "__main__":
    main()
