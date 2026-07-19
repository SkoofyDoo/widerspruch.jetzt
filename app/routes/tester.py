"""Beta tester magic-link endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from app.config import ADMIN_SECRET, APP_URL, DEFAULT_K, MAX_K, TESTER_MAX_USES, TESTER_TTL_DAYS
from app.generation.guards import validate_text
from app.generation.llm import LLMError
from app.generation.pipeline import extract_user_text, generate_widerspruch_letter, make_preview
from app.jobcenter import hydrate_jobcenter_from_db
from app.models import WiderspruchWorkflowRequest
from app.pdf.render import text_to_pdf_bytes
from app.rag.retrieve import build_quellen_unique
from app.routes.widerspruch import _export_letter, resolve_preview_download
from app.testers.tokens import (
    app_link_for_token,
    load_testers,
    mint_tester_token,
    save_testers,
    tester_check_or_403,
    tester_consume_or_403,
    tester_enabled,
    token_id,
)

router = APIRouter(tags=["tester"])


@router.post("/t/{token}/widerspruch/workflow")
def tester_widerspruch_workflow(
    token: str,
    req: WiderspruchWorkflowRequest,
    preview: Optional[str] = Query(None),
    download: Optional[str] = Query(None),
):
    if not tester_enabled():
        raise HTTPException(404, "Tester access not enabled")

    is_preview, is_download = resolve_preview_download(
        preview, download, bool(getattr(req, "preview", False))
    )
    if is_download:
        tester_consume_or_403(token)

    cached = (getattr(req, "letter_text", None) or "").strip()
    use_cache = bool(cached) and (is_download or not is_preview)

    if use_cache:
        letter, items, context = cached, [], None
    else:
        facts = hydrate_jobcenter_from_db(req.facts or {})
        k = max(1, min(MAX_K, int(req.k or DEFAULT_K)))
        style = (req.style or "standard").lower().strip()
        req_text = extract_user_text(req)

        try:
            letter, items, context = generate_widerspruch_letter(
                facts=facts, req_text=req_text, k=k, style=style, include_anlagen=True
            )
        except LLMError as e:
            raise HTTPException(503, str(e)) from e
        except RuntimeError as e:
            raise HTTPException(503, str(e)) from e

    if is_preview:
        preview_text = make_preview(letter)
        return Response(
            content=preview_text.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={
                "X-Preview": "1",
                "X-Full-Letter": "1",
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
            },
        )

    fmt = (req.format or "txt").lower().strip()
    if fmt in ("txt", "pdf"):
        return _export_letter(letter, fmt, req.filename)

    validation = validate_text(letter)
    quellen = build_quellen_unique(items, max_cites=8) if req.include_quellen and not use_cache else []
    return {
        "ok": bool(validation.get("ok")),
        "text": letter,
        "validation": validation,
        "quellen": quellen,
        "context": context if (req.include_context and not use_cache) else None,
    }


@router.get("/tester/whoami")
def tester_whoami(token: str):
    if not tester_enabled():
        raise HTTPException(404, "Tester access not enabled")
    payload = tester_check_or_403(token)
    tid = token_id(token)
    db = load_testers()
    rec = db.get(tid) or {}
    uses = int(rec.get("uses") or 0)
    max_uses = int(rec.get("max_uses") or TESTER_MAX_USES)
    return {
        "email": (payload.get("email") or "").strip(),
        "uses": uses,
        "max_uses": max_uses,
        "exp": payload.get("exp"),
        "token_id": tid,
    }


@router.post("/tester/mint")
def tester_mint(
    request: Request,
    email: str,
    days: int = TESTER_TTL_DAYS,
    max_uses: int = TESTER_MAX_USES,
):
    if not tester_enabled():
        raise HTTPException(400, "TESTER_SECRET is not set")
    if not ADMIN_SECRET:
        raise HTTPException(403, "ADMIN_SECRET is not set")

    admin = (request.headers.get("X-Admin-Secret") or request.query_params.get("admin") or "").strip()
    if admin != ADMIN_SECRET:
        raise HTTPException(403, "Forbidden")

    token = mint_tester_token(email=email, days=days)
    tid = token_id(token)
    db = load_testers()
    rec = db.get(tid) or {}
    rec.update({"uses": int(rec.get("uses") or 0), "max_uses": int(max_uses)})
    db[tid] = rec
    save_testers(db)

    return {
        "token": token,
        "email": (email or "").strip(),
        "app_link": app_link_for_token(token),
        "workflow_url": f"{APP_URL}/t/{token}/widerspruch/workflow",
        "token_id": tid,
        "days": int(days),
        "max_uses": int(max_uses),
    }
