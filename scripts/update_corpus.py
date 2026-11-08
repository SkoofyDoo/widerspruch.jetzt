#!/usr/bin/env python3
"""Refresh law corpus from GII XML: fetch ZIPs → parse → norms.jsonl + cleaned/.

Used by weekly corpus-cron (supercronic). Does not rebuild Chroma.
"""

from __future__ import annotations

import hashlib
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.parser.fetch_xml import RAW_XML_DIR, main as fetch_main  # noqa: E402
from app.parser.parse_xml import NORMS_JSONL, main as parse_main  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xml_fingerprint() -> dict[str, str]:
    if not RAW_XML_DIR.is_dir():
        return {}
    return {
        str(p.relative_to(RAW_XML_DIR)).replace("\\", "/"): _sha256(p)
        for p in sorted(RAW_XML_DIR.rglob("*.xml"))
    }


def main() -> int:
    print("=== corpus update: start ===", flush=True)
    before = xml_fingerprint()

    try:
        fetch_main()
    except Exception:
        traceback.print_exc()
        print("=== corpus update: fetch FAILED ===", flush=True)
        return 1

    after = xml_fingerprint()
    unchanged = bool(before) and before == after and NORMS_JSONL.is_file()

    if unchanged:
        print("XML unchanged — skip parse", flush=True)
        print("=== corpus update: done (no changes) ===", flush=True)
        return 0

    try:
        parse_main()
    except Exception:
        traceback.print_exc()
        print("=== corpus update: parse FAILED ===", flush=True)
        return 1

    print("=== corpus update: done ===", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
