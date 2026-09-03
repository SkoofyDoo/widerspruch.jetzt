"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
UI_DIR = ROOT_DIR / "ui"

# Project .env wins over stale shell exports (e.g. old OLLAMA_MODEL).
load_dotenv(ROOT_DIR / ".env", override=True)

# Silence Chroma/PostHog telemetry (benign errors like ClientStartEvent capture())
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["POSTHOG_DISABLED"] = "1"
os.environ["SCARF_NO_ANALYTICS"] = "true"

PREVIEW_CHARS = int(os.getenv("PREVIEW_CHARS", "1400"))
PREVIEW_HARD_CAP = 5000

STRIPE_MODE = (os.getenv("STRIPE_MODE") or "test").strip().lower()
APP_URL = (os.getenv("APP_URL") or "http://127.0.0.1:8008").strip().rstrip("/")

CHROMA_DIR = str(DATA_DIR / "chroma")
COLLECTION = os.getenv("CHROMA_COLLECTION", "laws_de")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen3-embedding:4b")
# auto | local | huggingface — auto uses HF when HF_TOKEN is set (Railway-safe)
EMBEDDING_PROVIDER = (os.getenv("EMBEDDING_PROVIDER") or "auto").strip().lower()
# Optional override for feature-extraction endpoint
HF_EMBED_API_URL = (os.getenv("HF_EMBED_API_URL") or "").strip()

JOB_CENTER_JSON = str(DATA_DIR / "jobcenter_de.json")
SUBS_DB = str(DATA_DIR / "subscriptions.json")
EVENTS_DB = str(DATA_DIR / "stripe_events.json")

# --- LLM providers ---
# ollama = local quality; huggingface = remote free/paid Inference Providers
LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "ollama").strip().lower()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

HF_TOKEN = (os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN") or "").strip()
HF_MODEL = os.getenv("HF_MODEL", "Qwen/Qwen2.5-7B-Instruct")
# OpenAI-compatible router (Inference Providers)
HF_API_URL = os.getenv(
    "HF_API_URL",
    "https://router.huggingface.co/v1/chat/completions",
).strip()
HF_TIMEOUT = int(os.getenv("HF_TIMEOUT", "90"))
HF_MAX_TOKENS = int(os.getenv("HF_MAX_TOKENS", "1200"))

# --- Public portfolio demo / paywall ---
# Portfolio default: OPEN access (full letter + free download). Set PAYWALL_ENABLED=true to re-enable Stripe gate.
PAYWALL_ENABLED = (os.getenv("PAYWALL_ENABLED") or "false").strip().lower() in (
    "1", "true", "yes", "on",
)
# DEMO_MODE defaults ON when paywall is off (banner + open access helpers)
_demo_default = "true" if not PAYWALL_ENABLED else "false"
DEMO_MODE = (os.getenv("DEMO_MODE") or _demo_default).strip().lower() in ("1", "true", "yes", "on")
# Free download defaults ON when paywall is off
_dl_default = "true" if not PAYWALL_ENABLED else "false"
DEMO_ALLOW_DOWNLOAD = (os.getenv("DEMO_ALLOW_DOWNLOAD") or _dl_default).strip().lower() in (
    "1", "true", "yes", "on",
)
# Full letter in "preview" response (no 🔒 truncation) when paywall off
FULL_LETTER_PREVIEW = (os.getenv("FULL_LETTER_PREVIEW") or ("true" if not PAYWALL_ENABLED else "false")).strip().lower() in (
    "1", "true", "yes", "on",
)
DEMO_MAX_PREVIEWS_PER_IP = int(os.getenv("DEMO_MAX_PREVIEWS_PER_IP", "30"))
DEMO_RATE_WINDOW_SEC = int(os.getenv("DEMO_RATE_WINDOW_SEC", "3600"))
DEMO_BANNER = os.getenv(
    "DEMO_BANNER",
    "Portfolio-Demo · voller Text + Download gratis · keine Rechtsberatung · rate-limited",
)

E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "

DEFAULT_K = 3
MAX_K = 20
RAG_OVERSAMPLE = 10
DISTANCE_CUTOFF = float(os.getenv("DISTANCE_CUTOFF", "0.22"))
# legacy = e5 / laws_de (Railway-safe); hybrid = Qwen + BM25 + RRF / wdjetzt (local)
RETRIEVER_BACKEND = (os.getenv("RETRIEVER_BACKEND") or "legacy").strip().lower()

STRICT_CITATIONS = True
NO_STRONG_CLAIMS = True

# Repair rounds: lower in DEMO_MODE to save HF quota (hard guards still apply)
_default_cit = "0" if DEMO_MODE else "1"
_default_strong = "0" if DEMO_MODE else "1"
MAX_REPAIR_ROUNDS_CIT = int(os.getenv("MAX_REPAIR_ROUNDS_CIT", _default_cit))
MAX_REPAIR_ROUNDS_STRONG = int(os.getenv("MAX_REPAIR_ROUNDS_STRONG", _default_strong))
# Second full-letter LLM pass (style only). Off in DEMO by default — doubles CPU latency.
_default_polish = "false" if DEMO_MODE else "true"
LLM_POLISH = (os.getenv("LLM_POLISH") or _default_polish).strip().lower() in (
    "1", "true", "yes", "on",
)

ANTRAEGE_WHITELIST = [
    "Eingangsbestätigung dieses Widerspruchs",
    "Akteneinsicht in die das Verfahren betreffenden Unterlagen zur Vorbereitung der Begründung (soweit zulässig)",
    "Schriftliche Erläuterung/Begründung des Bescheids (soweit erforderlich)",
    "Überprüfung des Bescheids und erneute Entscheidung",
    "Aufhebung der Minderung sowie entsprechende Neuberechnung der Leistungen (soweit einschlägig)",
]

ADMIN_SECRET = (os.getenv("ADMIN_SECRET") or "").strip()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_KEY = os.getenv("SMTP_KEY")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
FEEDBACK_TO = os.getenv("FEEDBACK_TO", "support@widerspruchjetzt.de")
