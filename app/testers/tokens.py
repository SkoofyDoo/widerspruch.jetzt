"""HMAC-signed beta tester tokens with TTL and use limits."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException

from app.config import APP_URL, TESTER_DB, TESTER_MAX_USES, TESTER_SECRET, TESTER_TTL_DAYS
from app.utils import load_json, now_utc, save_json


def tester_enabled() -> bool:
    return bool(TESTER_SECRET)


def b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")


def b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))


def token_id(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def load_testers() -> dict:
    return load_json(TESTER_DB, {})


def save_testers(db: dict) -> None:
    save_json(TESTER_DB, db)


def mint_tester_token(email: str, days: int = None) -> str:
    if not tester_enabled():
        raise RuntimeError("TESTER_SECRET is not set")
    days = int(days or TESTER_TTL_DAYS)
    exp = now_utc() + timedelta(days=days)
    payload = {
        "email": (email or "").strip().lower(),
        "exp": exp.isoformat().replace("+00:00", "Z"),
        "nonce": secrets.token_urlsafe(8),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(TESTER_SECRET.encode("utf-8"), raw, hashlib.sha256).digest()
    return f"{b64url_encode(raw)}.{b64url_encode(sig)}"


def verify_tester_token(token: str) -> Optional[dict]:
    if not tester_enabled():
        return None
    try:
        parts = (token or "").split(".")
        if len(parts) != 2:
            return None
        raw = b64url_decode(parts[0])
        sig = b64url_decode(parts[1])
        expected = hmac.new(TESTER_SECRET.encode("utf-8"), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(raw.decode("utf-8"))
        exp_raw = (payload.get("exp") or "").replace("Z", "+00:00")
        exp_dt = datetime.fromisoformat(exp_raw)
        if exp_dt <= now_utc():
            return None
        return payload
    except Exception:
        return None


def tester_check_or_403(token: str) -> dict:
    payload = verify_tester_token(token)
    if not payload:
        raise HTTPException(403, "Invalid or expired tester link")
    return payload


def tester_consume_or_403(token: str) -> dict:
    payload = tester_check_or_403(token)
    tid = token_id(token)
    db = load_testers()
    rec = db.get(tid) or {}
    uses = int(rec.get("uses") or 0)
    max_uses = int(rec.get("max_uses") or TESTER_MAX_USES)
    if uses >= max_uses:
        raise HTTPException(403, "Tester link usage limit reached")
    rec.update({
        "uses": uses + 1,
        "max_uses": max_uses,
        "email": payload.get("email"),
        "exp": payload.get("exp"),
        "last_used_at": now_utc().isoformat().replace("+00:00", "Z"),
    })
    db[tid] = rec
    save_testers(db)
    return payload


def derive_email_from_token(token: str) -> str:
    if not token or not tester_enabled():
        return ""
    payload = verify_tester_token(token)
    if not payload:
        return ""
    return (payload.get("email") or "").strip().lower()


def app_link_for_token(token: str) -> str:
    return f"{APP_URL}/ui/?token={token}"
