"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Silence Chroma/PostHog telemetry (benign errors like ClientStartEvent capture())
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["POSTHOG_DISABLED"] = "1"
os.environ["SCARF_NO_ANALYTICS"] = "true"


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
UI_DIR = ROOT_DIR / "ui"

PREVIEW_CHARS = int(os.getenv("PREVIEW_CHARS", "1400"))
PREVIEW_HARD_CAP = 5000

STRIPE_MODE = (os.getenv("STRIPE_MODE") or "test").strip().lower()
APP_URL = (os.getenv("APP_URL") or "http://127.0.0.1:8008").strip().rstrip("/")

CHROMA_DIR = str(DATA_DIR / "chroma")
COLLECTION = os.getenv("CHROMA_COLLECTION", "laws_de")
EMBEDDING_MODEL = "intfloat/multilingual-e5-base"

JOB_CENTER_JSON = str(DATA_DIR / "jobcenter_de.json")
SUBS_DB = str(DATA_DIR / "subscriptions.json")
EVENTS_DB = str(DATA_DIR / "stripe_events.json")
TESTER_DB = str(DATA_DIR / "tester_tokens.json")

# --- LLM providers ---
# ollama = local quality; huggingface = remote free/paid Inference Providers
LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "ollama").strip().lower()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b-instruct")
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

# --- Public portfolio demo ---
DEMO_MODE = (os.getenv("DEMO_MODE") or "false").strip().lower() in ("1", "true", "yes", "on")
DEMO_ALLOW_DOWNLOAD = (os.getenv("DEMO_ALLOW_DOWNLOAD") or "false").strip().lower() in (
    "1", "true", "yes", "on",
)
DEMO_MAX_PREVIEWS_PER_IP = int(os.getenv("DEMO_MAX_PREVIEWS_PER_IP", "20"))
DEMO_RATE_WINDOW_SEC = int(os.getenv("DEMO_RATE_WINDOW_SEC", "3600"))
DEMO_BANNER = os.getenv(
    "DEMO_BANNER",
    "Portfolio-Demo · keine Rechtsberatung · rate-limited · powered by RAG + LLM",
)

E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "

DEFAULT_K = 3
MAX_K = 20
RAG_OVERSAMPLE = 10
DISTANCE_CUTOFF = float(os.getenv("DISTANCE_CUTOFF", "0.22"))

STRICT_CITATIONS = True
NO_STRONG_CLAIMS = True

# Repair rounds: lower in DEMO_MODE to save HF quota (hard guards still apply)
_default_cit = "0" if DEMO_MODE else "1"
_default_strong = "0" if DEMO_MODE else "1"
MAX_REPAIR_ROUNDS_CIT = int(os.getenv("MAX_REPAIR_ROUNDS_CIT", _default_cit))
MAX_REPAIR_ROUNDS_STRONG = int(os.getenv("MAX_REPAIR_ROUNDS_STRONG", _default_strong))

ANTRAEGE_WHITELIST = [
    "Eingangsbestätigung dieses Widerspruchs",
    "Akteneinsicht in die das Verfahren betreffenden Unterlagen zur Vorbereitung der Begründung (soweit zulässig)",
    "Schriftliche Erläuterung/Begründung des Bescheids (soweit erforderlich)",
    "Überprüfung des Bescheids und erneute Entscheidung",
    "Aufhebung der Minderung sowie entsprechende Neuberechnung der Leistungen (soweit einschlägig)",
]

TESTER_SECRET = (os.getenv("TESTER_SECRET") or "").strip()
TESTER_TTL_DAYS = int(os.getenv("TESTER_TTL_DAYS") or "14")
TESTER_MAX_USES = int(os.getenv("TESTER_MAX_USES") or "30")
ADMIN_SECRET = (os.getenv("ADMIN_SECRET") or "").strip()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_KEY = os.getenv("SMTP_KEY")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
FEEDBACK_TO = os.getenv("FEEDBACK_TO", "support@widerspruchjetzt.de")
