"""Binary rebuild marker for Chroma: only ``true`` or ``false``.

Set to ``true`` by the XML parser when the corpus gains/changes paragraphs.
Cleared to ``false`` by ingest after a successful re-index.
"""

from __future__ import annotations

from pathlib import Path

# app/rag/v2/rebuild_flag.py → repo root is parents[3]
REBUILD_FLAG_PATH = Path(__file__).resolve().parents[3] / "data" / "chroma_rebuild.flag"

_TRUE = "true"
_FALSE = "false"


def read_rebuild_flag(path: Path = REBUILD_FLAG_PATH) -> bool:
    """Return True only when the file exists and contains ``true``."""
    if not path.is_file():
        return False
    value = path.read_text(encoding="utf-8").strip().lower()
    return value == _TRUE


def write_rebuild_flag(needed: bool, path: Path = REBUILD_FLAG_PATH) -> None:
    """Write exactly ``true`` or ``false`` (one line)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{_TRUE if needed else _FALSE}\n", encoding="utf-8")
    print(f"[REBUILD FLAG]: {path.name} = {_TRUE if needed else _FALSE}")
