"""Health, public config, and account status endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.billing.access import is_user_paid, load_subs
from app.config import STRIPE_MODE
from app.demo import public_config
from app.deps import chroma_status
from app.generation.llm import llm_status

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    status = {"ok": True, **chroma_status(), **llm_status(), **public_config()}
    # overall ok reflects chroma (required for RAG); llm is informational
    status["ok"] = bool(status.get("chroma_ok"))
    return status


@router.get("/config")
def config_public():
    """Frontend bootstrap flags (demo banner, payments off, etc.)."""
    return public_config()


@router.get("/me")
def me(user_id: str):
    db = load_subs()
    rec = db.get(user_id) or {}
    until = rec.get("access_until")
    active = is_user_paid(user_id)
    uses_left = int(rec.get("uses_left") or 0)
    return {
        "user_id": user_id,
        "active": active,
        "access_until": until,
        "uses_left": uses_left,
        "mode": STRIPE_MODE,
        **public_config(),
    }
