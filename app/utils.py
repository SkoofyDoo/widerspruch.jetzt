"""Shared helpers: JSON IO, dates, string sanitizers."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timezone
from typing import Any, Optional

from app.config import E5_PASSAGE_PREFIX

_DE_MONTHS = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
            if not raw:
                return default
            return json.loads(raw) or default
    except Exception:
        return default


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(s: str):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def fmt_de_long(d: date) -> str:
    return f"{d.day:02d}. {_DE_MONTHS[d.month - 1]} {d.year}"


def parse_yyyy_mm_dd(s: str) -> Optional[date]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        parts = s.split("-")
        if len(parts) != 3:
            return None
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        return date(y, m, d)
    except Exception:
        return None


def fmt_bescheid_date_display(raw: str) -> str:
    raw = (raw or "").strip()
    d = parse_yyyy_mm_dd(raw)
    if d:
        return fmt_de_long(d)
    return raw


def safe_str(x: Any) -> str:
    return (str(x).strip() if x is not None else "").strip()


def strip_passage_prefix(text: str) -> str:
    t = text or ""
    return t[len(E5_PASSAGE_PREFIX):] if t.startswith(E5_PASSAGE_PREFIX) else t


def normalize_citation_order(text: str) -> str:
    t = text or ""
    t = re.sub(
        r"\bSGB\s*(X|II|I{1,3}|IV|V|VI|VII|VIII|IX|XI|XII|II|2)\s*§\s*(\d+[a-z]?)\b",
        r"§ \2 SGB \1",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"\bSGB\s*2\b", "SGB II", t, flags=re.IGNORECASE)
    return t
