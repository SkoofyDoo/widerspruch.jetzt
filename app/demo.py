"""Portfolio DEMO_MODE helpers: open preview, optional download, IP rate limits."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request

from app import config

_lock = threading.Lock()
_preview_hits: Dict[str, Deque[float]] = defaultdict(deque)


def client_ip(request: Request | None) -> str:
    if request is None:
        return "unknown"
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def check_preview_rate_limit(request: Request | None) -> None:
    """Enforce DEMO_MAX_PREVIEWS_PER_IP within DEMO_RATE_WINDOW_SEC."""
    if not config.DEMO_MODE:
        return
    ip = client_ip(request)
    now = time.time()
    window = max(60, int(config.DEMO_RATE_WINDOW_SEC))
    limit = max(1, int(config.DEMO_MAX_PREVIEWS_PER_IP))

    with _lock:
        q = _preview_hits[ip]
        while q and (now - q[0]) > window:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(
                429,
                f"Demo rate limit: max {limit} previews per hour for this IP. "
                "See samples/letter_example.txt or try later.",
            )
        q.append(now)


def enforce_demo_download_policy(is_download: bool) -> None:
    if not config.DEMO_MODE or not is_download:
        return
    if not config.DEMO_ALLOW_DOWNLOAD:
        raise HTTPException(
            403,
            "Download is disabled in DEMO_MODE. Use preview, or set DEMO_ALLOW_DOWNLOAD=true.",
        )


def public_config() -> dict:
    """Safe config for UI (no secrets)."""
    return {
        "demo_mode": config.DEMO_MODE,
        "demo_allow_download": config.DEMO_ALLOW_DOWNLOAD,
        "demo_banner": config.DEMO_BANNER if config.DEMO_MODE else "",
        "llm_provider": config.LLM_PROVIDER,
        "llm_model": (
            config.HF_MODEL
            if config.LLM_PROVIDER in ("hf", "huggingface", "inference")
            else config.OLLAMA_MODEL
        ),
        "payments_enabled": (not config.DEMO_MODE),
    }
