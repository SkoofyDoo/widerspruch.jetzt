"""
LLM provider abstraction.

Supports:
  - ollama       local dev / high quality
  - huggingface  remote free/paid Inference Providers (OpenAI-compatible)

Env:
  LLM_PROVIDER=ollama|huggingface
  HF_TOKEN, HF_MODEL, HF_API_URL
  OLLAMA_URL, OLLAMA_MODEL
"""

from __future__ import annotations

import requests

from app import config


class LLMError(RuntimeError):
    """Raised when the configured LLM provider fails."""


def call_llm(prompt: str) -> str:
    """Generate text with the configured provider."""
    provider = (config.LLM_PROVIDER or "ollama").strip().lower()
    if provider in ("hf", "huggingface", "inference"):
        return _call_huggingface(prompt)
    if provider == "ollama":
        return _call_ollama(prompt)
    raise LLMError(f"Unknown LLM_PROVIDER={provider!r}. Use 'ollama' or 'huggingface'.")


def llm_status() -> dict:
    """Best-effort provider health (does not burn generation credits heavily)."""
    provider = (config.LLM_PROVIDER or "ollama").strip().lower()
    base = {
        "provider": provider,
        "model": _active_model(provider),
    }
    if provider in ("hf", "huggingface", "inference"):
        if not config.HF_TOKEN:
            return {**base, "llm_ok": False, "error": "HF_TOKEN not set"}
        # Lightweight authenticated call — no generation
        try:
            r = requests.get(
                "https://huggingface.co/api/whoami-v2",
                headers={"Authorization": f"Bearer {config.HF_TOKEN}"},
                timeout=5,
            )
            ok = r.status_code == 200
            return {
                **base,
                "llm_ok": ok,
                "api": config.HF_API_URL,
                "error": None if ok else f"HF auth HTTP {r.status_code}",
            }
        except Exception as e:
            return {**base, "llm_ok": False, "api": config.HF_API_URL, "error": str(e)}

    # ollama
    try:
        root = config.OLLAMA_URL
        if "/api/" in root:
            root = root.split("/api/")[0]
        r = requests.get(root, timeout=2)
        return {
            **base,
            "llm_ok": r.status_code < 500,
            "url": config.OLLAMA_URL,
        }
    except Exception as e:
        return {
            **base,
            "llm_ok": False,
            "url": config.OLLAMA_URL,
            "error": str(e),
        }


def _active_model(provider: str) -> str:
    if provider in ("hf", "huggingface", "inference"):
        return config.HF_MODEL
    return config.OLLAMA_MODEL


def _ollama_chat_url(configured: str) -> str:
    """Prefer /api/chat — think:false is reliable there for Qwen3 (generate often ignores it)."""
    root = configured.split("/api/")[0].rstrip("/") if "/api/" in configured else configured.rstrip("/")
    return f"{root}/api/chat"


def _call_ollama(prompt: str) -> str:
    # Qwen3 defaults to thinking mode: without think:false the model burns the
    # token budget on `thinking` and leaves `response`/`content` empty → UI timeout.
    url = _ollama_chat_url(config.OLLAMA_URL)
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.1, "top_p": 0.9},
    }
    try:
        r = requests.post(url, json=payload, timeout=config.OLLAMA_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        raise LLMError(f"Ollama request failed: {e}") from e
    data = r.json()
    text = ""
    msg = data.get("message")
    if isinstance(msg, dict):
        text = (msg.get("content") or "").strip()
    if not text:
        text = (data.get("response") or "").strip()
    if not text:
        raise LLMError("Ollama returned empty response (is think disabled?)")
    return text


def _call_huggingface(prompt: str) -> str:
    if not config.HF_TOKEN:
        raise LLMError("HF_TOKEN is not set (required for LLM_PROVIDER=huggingface)")

    headers = {
        "Authorization": f"Bearer {config.HF_TOKEN}",
        "Content-Type": "application/json",
    }
    # OpenAI-compatible chat completions (HF Inference Providers / router)
    payload = {
        "model": config.HF_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Du bist ein präziser Assistent für formelle deutsche Verwaltungstexte. "
                    "Folge strikt den Anweisungen im User-Prompt. Keine Meta-Kommentare."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": config.HF_MAX_TOKENS,
        "stream": False,
    }
    try:
        r = requests.post(
            config.HF_API_URL,
            headers=headers,
            json=payload,
            timeout=config.HF_TIMEOUT,
        )
    except requests.RequestException as e:
        raise LLMError(f"HuggingFace request failed: {e}") from e

    if r.status_code == 429:
        raise LLMError("HuggingFace rate limit / quota exceeded. Try again later.")
    if r.status_code >= 400:
        detail = r.text[:400]
        raise LLMError(f"HuggingFace HTTP {r.status_code}: {detail}")

    data = r.json()
    # OpenAI-style
    try:
        text = data["choices"][0]["message"]["content"]
        text = (text or "").strip()
        if text:
            return text
    except (KeyError, IndexError, TypeError):
        pass

    # Some gateways return generated_text
    if isinstance(data, dict) and data.get("generated_text"):
        return str(data["generated_text"]).strip()
    if isinstance(data, list) and data and isinstance(data[0], dict):
        if data[0].get("generated_text"):
            return str(data[0]["generated_text"]).strip()

    raise LLMError(f"Unexpected HuggingFace response shape: {str(data)[:300]}")
