"""Subscription / credit store and Stripe helpers (JSON-backed)."""

from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException

from app.config import APP_URL, EVENTS_DB, STRIPE_MODE, SUBS_DB
from app.deps import stripe
from app.utils import load_json, now_utc, parse_dt, save_json
import os


def stripe_webhook_secret() -> str:
    return (
        os.getenv("STRIPE_WEBHOOK_SECRET_LIVE")
        if STRIPE_MODE == "live"
        else os.getenv("STRIPE_WEBHOOK_SECRET_TEST") or ""
    ).strip()


def stripe_secret_key() -> str:
    return (
        os.getenv("STRIPE_SECRET_KEY_LIVE")
        if STRIPE_MODE == "live"
        else os.getenv("STRIPE_SECRET_KEY_TEST") or ""
    ).strip()


def stripe_price_id() -> str:
    return (
        os.getenv("STRIPE_PRICE_ID_LIVE")
        if STRIPE_MODE == "live"
        else os.getenv("STRIPE_PRICE_ID_TEST") or ""
    ).strip()


def require_stripe_config() -> None:
    if stripe is None:
        raise HTTPException(500, "Stripe not installed. pip install stripe")
    sk = stripe_secret_key()
    if not sk:
        raise HTTPException(500, "Missing Stripe secret key for current mode")
    stripe.api_key = sk
    if not stripe_webhook_secret():
        raise HTTPException(500, "Missing Stripe webhook secret for current mode")
    if not stripe_price_id():
        raise HTTPException(500, "Missing STRIPE_PRICE_ID for current mode")


def load_subs() -> dict:
    db = load_json(SUBS_DB, {})
    if not isinstance(db, dict):
        db = {}
    changed = False
    for uid, rec in list(db.items()):
        if not isinstance(rec, dict):
            db[uid] = {}
            rec = db[uid]
            changed = True
        for k, v in [
            ("access_until", ""),
            ("uses_left", 0),
            ("stripe_customer_id", ""),
            ("last_session_id", ""),
            ("last_charge_id", ""),
            ("last_payment_intent_id", ""),
            ("mode", STRIPE_MODE),
        ]:
            if k not in rec:
                rec[k] = v
                changed = True
    if changed:
        save_json(SUBS_DB, db)
    return db


def save_subs(db: dict) -> None:
    save_json(SUBS_DB, db)


def is_user_paid(user_id: str) -> bool:
    db = load_subs()
    rec = db.get(user_id) or {}
    until = rec.get("access_until")
    if not until:
        return False
    dt = parse_dt(until)
    if not dt:
        return False
    return dt > now_utc()


def set_user_access(
    user_id: str,
    days: int,
    stripe_customer_id: str = "",
    session_id: str = "",
    charge_id: str = "",
    payment_intent_id: str = "",
) -> None:
    db = load_subs()
    prev = db.get(user_id, {}) or {}
    now = now_utc()
    prev_until = parse_dt(prev.get("access_until") or "")
    base = prev_until if (prev_until and prev_until > now) else now
    access_until = (base + timedelta(days=days)).isoformat()
    prev_uses = int(prev.get("uses_left") or 0)
    uses_left = prev_uses + 1
    db[user_id] = {
        "access_until": access_until,
        "uses_left": uses_left,
        "stripe_customer_id": stripe_customer_id or prev.get("stripe_customer_id", ""),
        "last_session_id": session_id or prev.get("last_session_id", ""),
        "last_charge_id": charge_id or prev.get("last_charge_id", ""),
        "last_payment_intent_id": payment_intent_id or prev.get("last_payment_intent_id", ""),
        "mode": STRIPE_MODE,
    }
    save_json(SUBS_DB, db)


def revoke_access(user_id: str) -> None:
    db = load_subs()
    if user_id in db:
        db[user_id]["access_until"] = now_utc().isoformat()
        save_subs(db)


def find_user_by_charge(charge_id: str):
    if not charge_id:
        return None
    db = load_subs()
    for uid, rec in db.items():
        if (rec or {}).get("last_charge_id") == charge_id:
            return uid
    return None


def load_events_set() -> set:
    arr = load_json(EVENTS_DB, [])
    if not isinstance(arr, list):
        arr = []
    return set([x for x in arr if isinstance(x, str)])


def save_events_set(s: set) -> None:
    save_json(EVENTS_DB, sorted(list(s)))


def dedup_event(event_id: str) -> bool:
    if not event_id:
        return False
    seen = load_events_set()
    if event_id in seen:
        return True
    seen.add(event_id)
    save_events_set(seen)
    return False


def consume_use_or_402(user_id: str):
    """Consume one download credit or raise 402/429."""
    if not user_id:
        raise HTTPException(401, "Missing user_id")
    db = load_subs()
    rec = db.get(user_id) or {}
    until = rec.get("access_until")
    dt = parse_dt(until) if until else None
    if (not dt) or (dt <= now_utc()):
        raise HTTPException(402, "Payment required")
    uses_left = int(rec.get("uses_left") or 0)
    if uses_left <= 0:
        raise HTTPException(429, "No credits left. Please purchase again.")
    rec["uses_left"] = uses_left - 1
    db[user_id] = rec
    save_subs(db)
    return rec


def create_checkout_session(user_id: str, days: int):
    require_stripe_config()
    price_id = stripe_price_id()
    success_url = f"{APP_URL}/ui/?paid=1&user_id={user_id}"
    cancel_url = f"{APP_URL}/ui/?canceled=1&user_id={user_id}"
    days = max(1, min(int(days or 7), 365))
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": user_id, "days": str(days), "mode": STRIPE_MODE},
    )
    return {"url": session.url, "id": session.id}
