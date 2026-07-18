"""Jobcenter address lookup / fact hydration."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

from app.config import JOB_CENTER_JSON
from app.utils import load_json, safe_str

_JOB_CENTER_INDEX: Optional[Tuple[dict, dict]] = None


def load_jobcenter_index():
    data = load_json(JOB_CENTER_JSON, [])
    by_id = {}
    by_label = {}
    if isinstance(data, list):
        for rec in data:
            if not isinstance(rec, dict):
                continue
            rid = (rec.get("id") or "").strip()
            label = (rec.get("label") or "").strip()
            if rid:
                by_id[rid] = rec
            if label:
                key = re.sub(r"\s+", " ", label.lower()).strip()
                by_label[key] = rec
    return by_id, by_label


def ensure_jobcenter_index():
    global _JOB_CENTER_INDEX
    if _JOB_CENTER_INDEX is None:
        _JOB_CENTER_INDEX = load_jobcenter_index()
    return _JOB_CENTER_INDEX


def hydrate_jobcenter_from_db(facts: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(facts, dict):
        return facts or {}

    has_any = bool(
        safe_str(facts.get("jobcenter_address"))
        or safe_str(facts.get("jobcenter_postalCode") or facts.get("jobcenter_postal_code") or facts.get("jobcenter_plz"))
        or safe_str(facts.get("jobcenter_city"))
    )
    if has_any:
        return facts

    by_id, by_label = ensure_jobcenter_index()
    jc_id = safe_str(facts.get("jobcenter_id"))
    jc_label = safe_str(facts.get("jobcenter_label") or facts.get("jobcenter"))

    rec = None
    if jc_id and jc_id in by_id:
        rec = by_id[jc_id]
    elif jc_label:
        key = re.sub(r"\s+", " ", jc_label.lower()).strip()
        rec = by_label.get(key)

    if not rec:
        return facts

    if not safe_str(facts.get("jobcenter_label")) and safe_str(rec.get("label")):
        facts["jobcenter_label"] = rec.get("label")
    if not safe_str(facts.get("jobcenter_address")) and safe_str(rec.get("address")):
        facts["jobcenter_address"] = rec.get("address")
    if not safe_str(
        facts.get("jobcenter_postalCode") or facts.get("jobcenter_postal_code") or facts.get("jobcenter_plz")
    ) and safe_str(rec.get("postalCode")):
        facts["jobcenter_postalCode"] = rec.get("postalCode")
    if not safe_str(facts.get("jobcenter_city")) and safe_str(rec.get("city")):
        facts["jobcenter_city"] = rec.get("city")
    return facts
