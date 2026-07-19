"""Widerspruch workflow: preview + download (paywall optional)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from app import config
from app.billing.access import consume_use_or_402
from app.config import DEFAULT_K, MAX_K
from app.demo import check_preview_rate_limit, enforce_demo_download_policy, paywall_enabled
from app.generation.guards import validate_text
from app.generation.llm import LLMError
from app.generation.pipeline import extract_user_text, generate_widerspruch_letter, make_preview
from app.jobcenter import hydrate_jobcenter_from_db
from app.models import WiderspruchWorkflowRequest
from app.pdf.render import text_to_pdf_bytes
from app.rag.retrieve import build_quellen_unique

router = APIRouter(tags=["widerspruch"])


def resolve_preview_download(preview, download, body_preview: bool):
    """Resolve preview vs download flags (query overrides body)."""
    q_preview = (str(preview).lower() in ("1", "true", "yes", "y", "on")) if preview is not None else None
    q_download = (str(download).lower() in ("1", "true", "yes", "y", "on")) if download is not None else None

    if q_preview is not None or q_download is not None:
        if q_preview and q_download:
            raise HTTPException(400, "Choose either preview=1 or download=1, not both")
        is_download = bool(q_download)
        is_preview = bool(q_preview) or body_preview or (not is_download)
    else:
        is_preview = body_preview
        is_download = not is_preview
    return is_preview, is_download


@router.post("/widerspruch/workflow")
def widerspruch_workflow(
    req: WiderspruchWorkflowRequest,
    request: Request,
    preview: Optional[str] = Query(None),
    download: Optional[str] = Query(None),
):
    uid = (req.user_id or "").strip()
    if not uid:
        # Open portfolio / demo: allow anonymous
        if (not paywall_enabled()) or config.DEMO_MODE:
            uid = "demo-user"
        else:
            raise HTTPException(400, "Missing user_id")

    is_preview, is_download = resolve_preview_download(
        preview, download, bool(getattr(req, "preview", False))
    )

    # Rate-limit free generations in demo/open mode
    if is_preview or (is_download and not paywall_enabled()):
        check_preview_rate_limit(request)

    if is_download:
        enforce_demo_download_policy(True)
        # Only charge credits when paywall is explicitly enabled
        if paywall_enabled() and not (config.DEMO_MODE and config.DEMO_ALLOW_DOWNLOAD):
            consume_use_or_402(uid)

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
                "X-Full-Letter": "1" if config.FULL_LETTER_PREVIEW or not paywall_enabled() else "0",
                "X-Demo-Mode": "1" if config.DEMO_MODE or not paywall_enabled() else "0",
            },
        )

    validation = validate_text(letter)
    fmt = (req.format or "json").lower().strip()

    if fmt == "txt":
        out_name = (req.filename or "widerspruch.txt").strip()
        if not out_name.lower().endswith(".txt"):
            out_name += ".txt"
        return Response(
            content=letter.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
        )

    if fmt == "pdf":
        pdf_bytes = text_to_pdf_bytes(letter)
        out_name = (req.filename or "widerspruch.pdf").strip()
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
        )

    quellen = build_quellen_unique(items, max_cites=8) if req.include_quellen else []
    return {
        "ok": bool(validation.get("ok")),
        "text": letter,
        "validation": validation,
        "quellen": quellen,
        "context": context if req.include_context else None,
    }
