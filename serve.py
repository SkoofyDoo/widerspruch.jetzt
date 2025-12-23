# serve.py — SGB II + SGB X RAG Widerspruch API (strict official letter style)
# FULL WORKING FILE (copy-paste)
#
# PATCH (this round):
# 1) Krank+Attest + Termin/Minderung: remove §24/Anhörung paragraph (unless user explicitly mentions Anhörung)
# 2) Ensure "Aufhebung der Minderung + Neuberechnung" is ALWAYS included in the final Bitte-Absatz when %/Minderung/Kürzung/Meldeversäumnis is present
# 3) Prompt updated to avoid §24 boilerplate for Krank+Attest Termin cases
#
# Base path: /mnt/data/pasted.txt

import os
import re
import json
import traceback
import requests
import base64
import hashlib
import hmac
import secrets

from datetime import date, datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Literal
from io import BytesIO

from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

os.environ["ANONYMIZED_TELEMETRY"] = "FALSE"
os.environ["CHROMA_TELEMETRY"] = "FALSE"

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

try:
    import stripe
except Exception:
    stripe = None


# -----------------------------
# Config
# -----------------------------
PREVIEW_CHARS = int(os.getenv("PREVIEW_CHARS", "1400"))
PREVIEW_HARD_CAP = 5000

STRIPE_MODE = (os.getenv("STRIPE_MODE") or "test").strip().lower()
APP_URL = (os.getenv("APP_URL") or "http://127.0.0.1:8008").strip().rstrip("/")

CHROMA_DIR = os.path.join("data", "chroma")
COLLECTION = os.getenv("CHROMA_COLLECTION", "laws_de")

JOB_CENTER_JSON = os.path.join("data", "jobcenter_de.json")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b-instruct")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "

DEFAULT_K = 3
MAX_K = 20
RAG_OVERSAMPLE = 10
DISTANCE_CUTOFF = float(os.getenv("DISTANCE_CUTOFF", "0.22"))

STRICT_CITATIONS = True
MAX_REPAIR_ROUNDS_CIT = 1

NO_STRONG_CLAIMS = True
MAX_REPAIR_ROUNDS_STRONG = 1

ANTRAEGE_WHITELIST = [
    "Eingangsbestätigung dieses Widerspruchs",
    "Akteneinsicht in die das Verfahren betreffenden Unterlagen zur Vorbereitung der Begründung (soweit zulässig)",
    "Schriftliche Erläuterung/Begründung des Bescheids (soweit erforderlich)",
    "Überprüfung des Bescheids und erneute Entscheidung",
    "Aufhebung der Minderung sowie entsprechende Neuberechnung der Leistungen (soweit einschlägig)",
]

ANTRAEGE_BANNED_TERMS_RX = re.compile(
    r"\b(heilung|wiedereinsetzung|nichtig|nichtigkeit|ungültig|unwirksam|offensichtlich|schwerwiegend)\b",
    re.IGNORECASE
)

TESTER_SECRET = (os.getenv("TESTER_SECRET") or "").strip()
TESTER_TTL_DAYS = int(os.getenv("TESTER_TTL_DAYS") or "14")
TESTER_MAX_USES = int(os.getenv("TESTER_MAX_USES") or "30")
ADMIN_SECRET = (os.getenv("ADMIN_SECRET") or "").strip()

TESTER_DB = os.path.join("data", "tester_tokens.json")


# -----------------------------
# App init
# -----------------------------
app = FastAPI(title="SGB II + SGB X RAG API")

if os.path.isdir("ui"):
    app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")


# -----------------------------
# Chroma init
# -----------------------------
client = chromadb.PersistentClient(path=CHROMA_DIR)
embed_fn = SentenceTransformerEmbeddingFunction(model_name="intfloat/multilingual-e5-base")
try:
    col = client.get_collection(name=COLLECTION, embedding_function=embed_fn)
except Exception as e:
    raise RuntimeError(
        f"Chroma collection '{COLLECTION}' not found or failed to load. "
        f"CHROMA_DIR='{CHROMA_DIR}'. Run: python src/index.py. Original error: {e}"
    )


# -----------------------------
# JSON helpers
# -----------------------------
def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
            if not raw:
                return default
            return json.loads(raw) or default
    except Exception:
        return default


def _save_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _now_utc():
    return datetime.now(timezone.utc)


def _parse_dt(s: str):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


# -----------------------------
# German date helpers
# -----------------------------
_DE_MONTHS = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember"
]


def _fmt_de_long(d: date) -> str:
    return f"{d.day:02d}. {_DE_MONTHS[d.month - 1]} {d.year}"


def _parse_yyyy_mm_dd(s: str) -> Optional[date]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        parts = s.split("-")
        if len(parts) != 3:
            return None
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        return date(y, m, d)
    except Exception:
        return None


def _fmt_bescheid_date_display(raw: str) -> str:
    raw = (raw or "").strip()
    d = _parse_yyyy_mm_dd(raw)
    if d:
        return _fmt_de_long(d)
    return raw


# -----------------------------
# Stripe optional (unchanged)
# -----------------------------
SUBS_DB = os.path.join("data", "subscriptions.json")
EVENTS_DB = os.path.join("data", "stripe_events.json")


def _stripe_webhook_secret() -> str:
    return (os.getenv("STRIPE_WEBHOOK_SECRET_LIVE") if STRIPE_MODE == "live" else os.getenv("STRIPE_WEBHOOK_SECRET_TEST") or "").strip()


def _stripe_secret_key() -> str:
    return (os.getenv("STRIPE_SECRET_KEY_LIVE") if STRIPE_MODE == "live" else os.getenv("STRIPE_SECRET_KEY_TEST") or "").strip()


def _stripe_price_id() -> str:
    return (os.getenv("STRIPE_PRICE_ID_LIVE") if STRIPE_MODE == "live" else os.getenv("STRIPE_PRICE_ID_TEST") or "").strip()


def _require_stripe_config():
    if stripe is None:
        raise HTTPException(500, "Stripe not installed. pip install stripe")

    sk = _stripe_secret_key()
    if not sk:
        raise HTTPException(500, "Missing Stripe secret key for current mode")
    stripe.api_key = sk

    if not _stripe_webhook_secret():
        raise HTTPException(500, "Missing Stripe webhook secret for current mode")
    if not _stripe_price_id():
        raise HTTPException(500, "Missing STRIPE_PRICE_ID for current mode")


def _load_subs() -> dict:
    db = _load_json(SUBS_DB, {})
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
        _save_json(SUBS_DB, db)
    return db


def _save_subs(db: dict):
    _save_json(SUBS_DB, db)


def _is_user_paid(user_id: str) -> bool:
    db = _load_subs()
    rec = db.get(user_id) or {}
    until = rec.get("access_until")
    if not until:
        return False
    dt = _parse_dt(until)
    if not dt:
        return False
    return dt > _now_utc()


def _set_user_access(user_id: str, days: int, stripe_customer_id: str = "", session_id: str = "", charge_id: str = "", payment_intent_id: str = ""):
    db = _load_subs()
    prev = db.get(user_id, {}) or {}
    now = _now_utc()
    prev_until = _parse_dt(prev.get("access_until") or "")
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
    _save_json(SUBS_DB, db)


def _revoke_access(user_id: str):
    db = _load_subs()
    if user_id in db:
        db[user_id]["access_until"] = _now_utc().isoformat()
        _save_subs(db)


def _find_user_by_charge(charge_id: str):
    if not charge_id:
        return None
    db = _load_subs()
    for uid, rec in db.items():
        if (rec or {}).get("last_charge_id") == charge_id:
            return uid
    return None


def _load_events_set() -> set:
    arr = _load_json(EVENTS_DB, [])
    if not isinstance(arr, list):
        arr = []
    return set([x for x in arr if isinstance(x, str)])


def _save_events_set(s: set):
    _save_json(EVENTS_DB, sorted(list(s)))


def _dedup_event(event_id: str) -> bool:
    if not event_id:
        return False
    seen = _load_events_set()
    if event_id in seen:
        return True
    seen.add(event_id)
    _save_events_set(seen)
    return False


def _consume_use_or_402(user_id: str):
    if not user_id:
        raise HTTPException(401, "Missing user_id")
    db = _load_subs()
    rec = db.get(user_id) or {}
    until = rec.get("access_until")
    dt = _parse_dt(until) if until else None
    if (not dt) or (dt <= _now_utc()):
        raise HTTPException(402, "Payment required")
    uses_left = int(rec.get("uses_left") or 0)
    if uses_left <= 0:
        raise HTTPException(429, "No credits left. Please purchase again.")
    rec["uses_left"] = uses_left - 1
    db[user_id] = rec
    _save_subs(db)
    return rec


# -----------------------------
# Tester helpers
# -----------------------------
def _tester_enabled() -> bool:
    return bool(TESTER_SECRET)


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))


def _token_id(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def _load_testers() -> dict:
    return _load_json(TESTER_DB, {})


def _save_testers(db: dict):
    _save_json(TESTER_DB, db)


def _mint_tester_token(email: str, days: int = None) -> str:
    if not _tester_enabled():
        raise RuntimeError("TESTER_SECRET is not set")
    days = int(days or TESTER_TTL_DAYS)
    exp = _now_utc() + timedelta(days=days)
    payload = {
        "email": (email or "").strip().lower(),
        "exp": exp.isoformat().replace("+00:00", "Z"),
        "nonce": secrets.token_urlsafe(8),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(TESTER_SECRET.encode("utf-8"), raw, hashlib.sha256).digest()
    return f"{_b64url_encode(raw)}.{_b64url_encode(sig)}"


def _verify_tester_token(token: str) -> Optional[dict]:
    if not _tester_enabled():
        return None
    try:
        parts = (token or "").split(".")
        if len(parts) != 2:
            return None
        raw = _b64url_decode(parts[0])
        sig = _b64url_decode(parts[1])
        expected = hmac.new(TESTER_SECRET.encode("utf-8"), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(raw.decode("utf-8"))
        exp_raw = (payload.get("exp") or "").replace("Z", "+00:00")
        exp_dt = datetime.fromisoformat(exp_raw)
        if exp_dt <= _now_utc():
            return None
        return payload
    except Exception:
        return None


def _tester_check_or_403(token: str) -> dict:
    payload = _verify_tester_token(token)
    if not payload:
        raise HTTPException(403, "Invalid or expired tester link")
    return payload


def _tester_consume_or_403(token: str) -> dict:
    payload = _tester_check_or_403(token)

    tid = _token_id(token)
    db = _load_testers()
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
        "last_used_at": _now_utc().isoformat().replace("+00:00", "Z"),
    })
    db[tid] = rec
    _save_testers(db)
    return payload


def _escape_html(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


# -----------------------------
# Models
# -----------------------------
Language = Literal["de", "ru", "en", "uk", "tr", "ar"]
Style = Literal["standard", "formal", "short"]
OutFormat = Literal["txt", "pdf", "json"]


class SearchHit(BaseModel):
    id: str
    score: float
    text: str
    source_file: str
    law: str = ""
    paragraph: str = ""


class WiderspruchRequest(BaseModel):
    text: Optional[str] = None
    question: Optional[str] = None
    facts: Dict[str, Any] = Field(default_factory=dict)
    k: int = DEFAULT_K
    language: Language = "de"
    style: Style = "standard"
    include_quellen: bool = False
    include_context: bool = False


class ValidateRequest(BaseModel):
    text: str


class WiderspruchWorkflowRequest(BaseModel):
    user_id: Optional[str] = None
    text: Optional[str] = None
    question: Optional[str] = None
    facts: Optional[Dict[str, Any]] = None
    k: int = DEFAULT_K
    format: OutFormat = "txt"
    filename: Optional[str] = None
    language: Language = "de"
    style: Style = "standard"
    include_quellen: bool = False
    include_context: bool = False
    preview: bool = False


class PdfRequest(BaseModel):
    text: str
    filename: str = "widerspruch.pdf"


class CheckoutRequest(BaseModel):
    user_id: str
    days: int = 7


# -----------------------------
# Helpers
# -----------------------------
def _safe_str(x: Any) -> str:
    return (str(x).strip() if x is not None else "").strip()


def _strip_passage_prefix(text: str) -> str:
    t = text or ""
    return t[len(E5_PASSAGE_PREFIX):] if t.startswith(E5_PASSAGE_PREFIX) else t


def extract_user_text(obj: Any) -> str:
    facts = getattr(obj, "facts", None) or {}
    text = (getattr(obj, "text", None) or "") or (getattr(obj, "question", None) or "") or (facts.get("bescheid_text") or "")
    text = (text or "").strip()
    if not text:
        raise HTTPException(422, "Missing input text. Provide 'text', 'question' or 'facts.bescheid_text'.")
    return text


def _call_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "top_p": 0.9},
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return (data.get("response") or "").strip()


def _normalize_citation_order(text: str) -> str:
    t = text or ""
    t = re.sub(
        r"\bSGB\s*(X|II|I{1,3}|IV|V|VI|VII|VIII|IX|XI|XII)\s*§\s*(\d+[a-z]?)\b",
        r"§ \2 SGB \1",
        t,
        flags=re.IGNORECASE
    )
    t = re.sub(r"\bSGB\s*2\b", "SGB II", t, flags=re.IGNORECASE)
    return t


def _sanitize_widerspruch_text(t: str) -> str:
    if not t:
        return ""
    t = re.sub(r"^\s*#{1,6}\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"\bwiderruf\b", "Widerspruch", t, flags=re.IGNORECASE)
    t = re.sub(r"\bwiderrufen\b", "Widerspruch einlegen", t, flags=re.IGNORECASE)
    t = re.sub(r"(§\s*31a)\s*SGB\s*X\b", r"\1 SGB II", t, flags=re.IGNORECASE)
    t = _normalize_citation_order(t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)

    t = re.sub(r"\bWiderrufsprozesse?\b", "Verfahrensabläufe", t, flags=re.IGNORECASE)
    t = re.sub(r"\bWiderrufsprozess(?:e)?\b", "Verfahrensablauf", t, flags=re.IGNORECASE)
    t = re.sub(r"\bKopie des Bescheid\b", "Kopie des Bescheids", t, flags=re.IGNORECASE)
    t = re.sub(r"\bKopie vom Bescheid\b", "Kopie des Bescheids", t, flags=re.IGNORECASE)

    # German phrasing fixes
    t = re.sub(r"\beinen\s+ärztlichen\s+Bescheinigung\b", "eine ärztliche Bescheinigung", t, flags=re.IGNORECASE)
    t = re.sub(r"\bärztlichen\s+Bescheinigung\b", "ärztliche Bescheinigung", t, flags=re.IGNORECASE)
    t = re.sub(r"\bKrankheitstellung\b", "Erkrankung", t, flags=re.IGNORECASE)
    t = re.sub(r"\bmeine\s+Arbeit\s+zu\s+versehen\b", "den Termin wahrzunehmen", t, flags=re.IGNORECASE)
    t = re.sub(r"\barbeit\s+zu\s+versehen\b", "den Termin wahrzunehmen", t, flags=re.IGNORECASE)

    # remove filler
    t = re.sub(r"\brelevante\s+Zeitperiode\b", "den betreffenden Zeitraum", t, flags=re.IGNORECASE)

    return t.strip()


# -----------------------------
# HALLUCINATION / TOPIC GUARDS
# -----------------------------
_WORK_TERMS_RX = re.compile(
    r"\b(Arbeit(?:geber|sstelle)?|Job|Beschäftigung|Tätigkeit|Arbeitsstelle|Arbeitsverhältnis)\b",
    re.IGNORECASE
)
_TERMIN_TERMS_RX = re.compile(
    r"\b(Termin|Meldeversäumnis|Meldeaufforderung|Einladung)\b",
    re.IGNORECASE
)
_KRANK_TERMS_RX = re.compile(
    r"\b(krank|Krankheit|Attest|ärztlich|Arbeitsunfähigkeit|AU)\b",
    re.IGNORECASE
)

# For new patch
_ANHOERUNG_RX = re.compile(r"\b(Anhörung|§\s*24\s*SGB\s*X)\b", re.IGNORECASE)
_MINDERUNG_RX = re.compile(r"\b(kürzung|minderung|leistung(en)?\s*um|%|prozent|terminversäumnis|meldeversäumnis)\b", re.IGNORECASE)

def _is_krank_attest_termin_case(req_text: str) -> bool:
    rt = (req_text or "")
    return bool(_TERMIN_TERMS_RX.search(rt)) and bool(_KRANK_TERMS_RX.search(rt)) and bool(_MINDERUNG_RX.search(rt))

def _user_explicitly_mentions_anhörung(req_text: str) -> bool:
    rt = (req_text or "")
    return bool(re.search(r"\banhörung\b|§\s*24\b", rt, flags=re.IGNORECASE))

def _guard_remove_work_context_if_not_in_user_text(letter: str, req_text: str) -> str:
    lt = letter or ""
    ut = req_text or ""

    user_mentions_work = bool(_WORK_TERMS_RX.search(ut))
    user_mentions_termin = bool(_TERMIN_TERMS_RX.search(ut)) or ("termin" in ut.lower())
    user_mentions_km = bool(_KRANK_TERMS_RX.search(ut))

    if user_mentions_termin and user_mentions_km and (not user_mentions_work):
        lt = re.sub(r"\bmeine\s+Arbeit\s+zu\s+versehen\b", "den Termin wahrzunehmen", lt, flags=re.IGNORECASE)
        lt = re.sub(r"\bmeiner\s+Arbeit\b", "dem Termin", lt, flags=re.IGNORECASE)
        lt = re.sub(r"\bArbeitsstelle\b|\bArbeitgeber\b|\bArbeitsverhältnis\b", "", lt, flags=re.IGNORECASE)
        lt = re.sub(r"[ \t]{2,}", " ", lt)
        lt = re.sub(r"\n{3,}", "\n\n", lt)
        lt = lt.strip()

    return lt


def _guard_remove_anhörung_para_for_krank_attest(letter: str, req_text: str) -> str:
    """
    Patch: if it's a Krank+Attest + Termin/Minderung case AND user did NOT explicitly mention Anhörung,
    remove paragraphs that contain §24 SGB X / Anhörung boilerplate.
    Keep the letter coherent and add a neutral sentence if needed.
    """
    if not _is_krank_attest_termin_case(req_text):
        return letter
    if _user_explicitly_mentions_anhörung(req_text):
        return letter

    t = (letter or "").replace("\r\n", "\n").replace("\r", "\n")
    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    if not paras:
        return letter

    removed = False
    new_paras = []
    for p in paras:
        # remove only body paras containing Anhörung/§24; keep header blocks safe
        if _ANHOERUNG_RX.search(p):
            # avoid removing header if something weird matches there; only remove if it looks like a body paragraph
            if "Sehr geehrte" in p or "Betreff:" in p or "Mit freundlichen Grüßen" in p:
                new_paras.append(p)
            else:
                removed = True
            continue
        new_paras.append(p)

    if removed:
        # Ensure there is still a short "wichtiger Grund" style paragraph somewhere in body
        joined = "\n\n".join(new_paras)
        if not re.search(r"\bwichtiger\s+Grund\b", joined, flags=re.IGNORECASE):
            insert_text = (
                "Ich bitte um Prüfung des Vorgangs unter Berücksichtigung meiner Erkrankung als wichtiger Grund "
                "sowie um eine entsprechende Neubewertung."
            )
            # Insert before the last request paragraph if possible
            # Find paragraph that starts with "Ich bitte" and insert before it
            inserted = False
            out2 = []
            for p in new_paras:
                if (not inserted) and re.match(r"^Ich bitte\b", p, flags=re.IGNORECASE):
                    out2.append(insert_text)
                    inserted = True
                out2.append(p)
            new_paras = out2 if inserted else (new_paras + [insert_text])

        t2 = "\n\n".join(new_paras)
        t2 = _sanitize_widerspruch_text(t2)
        return t2

    return letter


# -----------------------------
# Jobcenter address hydration
# -----------------------------
def _load_jobcenter_index():
    data = _load_json(JOB_CENTER_JSON, [])
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


_JOB_CENTER_INDEX = None


def _ensure_jobcenter_index():
    global _JOB_CENTER_INDEX
    if _JOB_CENTER_INDEX is None:
        _JOB_CENTER_INDEX = _load_jobcenter_index()
    return _JOB_CENTER_INDEX


def _hydrate_jobcenter_from_db(facts: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(facts, dict):
        return facts or {}

    has_any = bool(_safe_str(facts.get("jobcenter_address")) or _safe_str(facts.get("jobcenter_postalCode") or facts.get("jobcenter_postal_code") or facts.get("jobcenter_plz")) or _safe_str(facts.get("jobcenter_city")))
    if has_any:
        return facts

    by_id, by_label = _ensure_jobcenter_index()

    jc_id = _safe_str(facts.get("jobcenter_id"))
    jc_label = _safe_str(facts.get("jobcenter_label") or facts.get("jobcenter"))

    rec = None
    if jc_id and jc_id in by_id:
        rec = by_id[jc_id]
    elif jc_label:
        key = re.sub(r"\s+", " ", jc_label.lower()).strip()
        rec = by_label.get(key)

    if not rec:
        return facts

    if not _safe_str(facts.get("jobcenter_label")) and _safe_str(rec.get("label")):
        facts["jobcenter_label"] = rec.get("label")

    if not _safe_str(facts.get("jobcenter_address")) and _safe_str(rec.get("address")):
        facts["jobcenter_address"] = rec.get("address")

    if not _safe_str(facts.get("jobcenter_postalCode") or facts.get("jobcenter_postal_code") or facts.get("jobcenter_plz")) and _safe_str(rec.get("postalCode")):
        facts["jobcenter_postalCode"] = rec.get("postalCode")

    if not _safe_str(facts.get("jobcenter_city")) and _safe_str(rec.get("city")):
        facts["jobcenter_city"] = rec.get("city")

    return facts


# -----------------------------
# Official-letter style enforcement
# -----------------------------
_STYLE_FORBIDDEN_HEADINGS_RX = re.compile(
    r"^\s*(KURZER\s+SACHVERHALT|SACHVERHALT|RECHTLICHE\s+PUNKTE|RECHTLICHE\s+HINWEISE|ANTRÄGE|ANTRAG|BEGRÜNDUNG)\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE
)
_STYLE_FORBIDDEN_ENUM_RX = re.compile(r"^\s*[A-Z]\)\s+.*$", re.MULTILINE)
_STYLE_FORBIDDEN_BULLET_RX = re.compile(r"^\s*[-•]\s+.*$", re.MULTILINE)
_STYLE_FORBIDDEN_ANLAGEN_RX = re.compile(r"^\s*Anlagen\s*:.*$", re.IGNORECASE)
_STYLE_FORBIDDEN_ANLAGEN_ITEM_RX = re.compile(r"^\s*(?:-|\u2022)?\s*Kopie\s+(?:des|vom)\s+Bescheid", re.IGNORECASE)


def _remove_klaeger_terms(text: str) -> str:
    t = text or ""
    t = re.sub(r"\bDer\s+Kläger\b", "Ich", t, flags=re.IGNORECASE)
    t = re.sub(r"\bKläger\b", "Widerspruchsführer", t, flags=re.IGNORECASE)
    return t


def _flatten_list_block(lines: List[str]) -> str:
    items = []
    for ln in lines:
        ln = re.sub(r"^\s*[-•]\s+", "", ln).strip()
        ln = re.sub(r"\s*;\s*$", "", ln).strip()
        if ln:
            items.append(ln)
    if not items:
        return ""
    s = "; ".join(items)
    if not s.endswith("."):
        s += "."
    return s


def _enforce_official_no_lists(body: str) -> str:
    t = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    t = _remove_klaeger_terms(t)

    t = "\n".join([ln for ln in t.split("\n") if not _STYLE_FORBIDDEN_ANLAGEN_RX.match(ln)])
    t = "\n".join([ln for ln in t.split("\n") if not _STYLE_FORBIDDEN_ANLAGEN_ITEM_RX.match(ln)])

    t = _STYLE_FORBIDDEN_HEADINGS_RX.sub("", t)
    t = _STYLE_FORBIDDEN_ENUM_RX.sub("", t)

    out_lines = []
    buf_bullets = []

    for raw in t.split("\n"):
        ln = raw.rstrip()

        if _STYLE_FORBIDDEN_BULLET_RX.match(ln):
            buf_bullets.append(ln)
            continue

        if buf_bullets:
            flat = _flatten_list_block(buf_bullets)
            if flat:
                out_lines.append(flat)
            buf_bullets = []

        out_lines.append(ln)

    if buf_bullets:
        flat = _flatten_list_block(buf_bullets)
        if flat:
            out_lines.append(flat)

    t2 = "\n".join(out_lines)
    t2 = re.sub(r"\n{3,}", "\n\n", t2).strip()

    if not t2.strip():
        t2 = "Ich bitte um Prüfung des Bescheids und um eine erneute Entscheidung."

    return t2


# -----------------------------
# Bitte paragraph (enforced)
# -----------------------------
_BITTE_START_RX = re.compile(r"^\s*(Ich bitte(?: Sie)? um|Bitte bestätigen Sie|Ich bitte Sie um)\b", re.IGNORECASE)
_BITTE_CONTAINS_RX = re.compile(r"\b(Eingangsbestätigung|Akteneinsicht|Erläuterung|Begründung|erneute Entscheidung|Überprüfung|Aufhebung|Neuberechnung)\b", re.IGNORECASE)
_BITTE_SOFT_RX = re.compile(
    r"^\s*(?:Bitte\s+prüfen\s+Sie\b|Ich\s+bitte\s+Sie\s+(?:daher|darum),\s*(?:den\s+Vorgang|den\s+Bescheid).{0,120}\bzu\s+prüfen\b)",
    re.IGNORECASE | re.DOTALL
)

def _build_safe_bitte_paragraph(req_text: str) -> str:
    rt = (req_text or "")
    wants_akte = bool(re.search(r"\bakteneinsicht\b", rt, flags=re.IGNORECASE))
    wants_begruendung = bool(re.search(r"\bbegründung\b|\berläuterung\b|\bnachvollziehbar\b", rt, flags=re.IGNORECASE))
    wants_minderung_aufhebung = bool(_MINDERUNG_RX.search(rt))

    parts = [ANTRAEGE_WHITELIST[0]]
    if wants_akte:
        parts.append(ANTRAEGE_WHITELIST[1])
    if wants_begruendung:
        parts.append(ANTRAEGE_WHITELIST[2])
    parts.append(ANTRAEGE_WHITELIST[3])
    if wants_minderung_aufhebung:
        parts.append(ANTRAEGE_WHITELIST[4])

    return "Ich bitte um " + "; ".join(parts) + "."

def _dedupe_and_fix_bitte_paragraphs(head_text: str, req_text: str) -> str:
    t = (head_text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = _remove_klaeger_terms(t)

    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    if not paras:
        return _build_safe_bitte_paragraph(req_text)

    found_idx = []
    for i, p in enumerate(paras):
        if _BITTE_START_RX.search(p) or _BITTE_SOFT_RX.search(p) or (_BITTE_CONTAINS_RX.search(p) and "Mit freundlichen Grüßen" not in p):
            found_idx.append(i)

    if not found_idx:
        paras.append(_build_safe_bitte_paragraph(req_text))
        return "\n\n".join(paras).strip()

    keep = found_idx[-1]

    new_paras = []
    for i, p in enumerate(paras):
        if i in found_idx and i != keep:
            continue
        new_paras.append(p)

    kept_para = paras[keep]
    keep_new = 0
    for i, p in enumerate(new_paras):
        if p == kept_para:
            keep_new = i
            break

    # If banned terms / too long / missing Eingangsbestätigung => replace
    kept = new_paras[keep_new]
    if ANTRAEGE_BANNED_TERMS_RX.search(kept) or len(kept) > 520:
        new_paras[keep_new] = _build_safe_bitte_paragraph(req_text)

    if not re.search(r"\bEingangsbestätigung\b", new_paras[keep_new], flags=re.IGNORECASE):
        new_paras[keep_new] = _build_safe_bitte_paragraph(req_text)

    # PATCH: If Minderung/% case => FORCE Aufhebung+Neuberechnung in the final Bitte paragraph
    if bool(_MINDERUNG_RX.search(req_text or "")):
        if not re.search(r"\bAufhebung\b|\bNeuberechnung\b", new_paras[keep_new], flags=re.IGNORECASE):
            new_paras[keep_new] = _build_safe_bitte_paragraph(req_text)

    # Drop redundant soft request paragraphs
    kept_now = new_paras[keep_new]
    if _BITTE_START_RX.search(kept_now):
        cleaned = []
        for idx, p in enumerate(new_paras):
            if idx != keep_new and _BITTE_SOFT_RX.search(p):
                continue
            cleaned.append(p)
        new_paras = cleaned

    return "\n\n".join(new_paras).strip()


# -----------------------------
# Validation
# -----------------------------
def _validate_text(text: str) -> Dict[str, Any]:
    t = (text or "").strip()
    warnings, errors = [], []

    if not re.search(r"Sehr geehrte Damen und Herren", t, flags=re.IGNORECASE):
        errors.append("Missing standard greeting 'Sehr geehrte Damen und Herren,'.")

    if re.search(r"\bWiderruf\b|\bwiderrufen\b|\bwiderrufe\b", t, flags=re.IGNORECASE):
        errors.append("Contains Widerruf/Widerrufen. Must be Widerspruch (not Widerruf).")

    if re.search(r"\bWiderspruch\b", t, flags=re.IGNORECASE) is None:
        errors.append("Missing keyword 'Widerspruch' in the letter text.")

    if re.search(r"\bKläger\b", t, flags=re.IGNORECASE):
        warnings.append("Contains 'Kläger' — should be avoided in Widerspruch (court term).")

    if _STYLE_FORBIDDEN_BULLET_RX.search(t):
        warnings.append("Contains bullet list lines — should be paragraphs for official letter style.")

    if _STYLE_FORBIDDEN_ENUM_RX.search(t):
        warnings.append("Contains A)/B) style enumerations — should be avoided.")

    ok = (len(errors) == 0)
    return {"ok": ok, "errors": errors, "warnings": warnings, "counts": {"errors": len(errors), "warnings": len(warnings)}}


# -----------------------------
# RAG retrieve
# -----------------------------
PROC_KEYWORDS = [
    "bescheid", "widerspruch", "anhörung", "akteneinsicht", "frist", "zustellung",
    "verwaltungsakt", "begründung", "formfehler", "verfahrensfehler", "überprüfung",
    "rücknahme", "widerruf", "sozialgericht", "eilantrag", "aufschiebende wirkung",
    "wiedereinsetzung"
]

def _is_procedural_query(q: str) -> bool:
    ql = (q or "").lower()
    return any(k in ql for k in PROC_KEYWORDS)

def _extract_allowed_paragraphs_from_query(q: str):
    m = re.search(r"§\s*(\d+[a-z]?)", q, flags=re.IGNORECASE)
    if not m:
        return None
    wanted = m.group(1).lower()
    allowed = {wanted, f"§ {wanted}"}
    if wanted in {"31", "31a", "31b", "32"}:
        for x in ["31", "31a", "31b", "32"]:
            allowed.add(x)
            allowed.add(f"§ {x}")
    return allowed

def _is_good_chunk(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return ("(1)" in t) or ("(2)" in t) or ("(3)" in t)

def _norm_paragraph(p: str) -> str:
    p = (p or "").strip().lower()
    if not p:
        return ""
    return p.replace("§", "").strip()

def _collect_items_from_res(res, q: str, allowed, require_absatz: bool, k: int, seen: set, existing=None):
    items = list(existing or [])
    ids = res.get("ids", [[]])[0]
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    procedural = _is_procedural_query(q)

    allowed_norm = {_norm_paragraph(a) for a in (allowed or set())} if allowed is not None else None

    for i in range(min(len(ids), len(docs))):
        dist = float(dists[i]) if i < len(dists) else 999.0
        if dist > DISTANCE_CUTOFF:
            continue

        meta = metas[i] or {}
        text = _strip_passage_prefix(docs[i])

        if require_absatz and (not _is_good_chunk(text)) and (not procedural):
            continue

        if allowed_norm is not None:
            mp = (meta.get("paragraph") or "").strip()
            mp_norm = _norm_paragraph(mp)
            if mp_norm and mp_norm not in allowed_norm:
                continue

        key = (meta.get("law", ""), meta.get("paragraph", ""), meta.get("source_file", ""), text[:140])
        if key in seen:
            continue
        seen.add(key)

        items.append({
            "id": ids[i],
            "source_file": meta.get("source_file", ""),
            "law": meta.get("law", ""),
            "paragraph": meta.get("paragraph", ""),
            "distance": dist,
            "text": text,
        })
        if len(items) >= k:
            break

    return items

def _retrieve(q: str, k: int, require_absatz: bool = True):
    k = max(1, min(MAX_K, int(k or DEFAULT_K)))
    take = max(60, k * RAG_OVERSAMPLE)
    allowed = _extract_allowed_paragraphs_from_query(q)
    procedural = _is_procedural_query(q)

    def _run_query(where=None, take_n=take):
        return col.query(
            query_texts=[E5_QUERY_PREFIX + q],
            n_results=take_n,
            include=["documents", "metadatas", "distances"],
            where=where
        )

    items = []
    seen = set()

    if procedural:
        try:
            res1 = _run_query(where={"law": "SGB X"}, take_n=take)
            items = _collect_items_from_res(res1, q, allowed, require_absatz, k, seen, existing=items)
            if len(items) >= k:
                return items
        except Exception:
            pass

    res2 = _run_query(where=None, take_n=take)
    items = _collect_items_from_res(res2, q, allowed, require_absatz, k, seen, existing=items)
    return items

def _build_context(items) -> str:
    return "\n\n".join(
        f"[{it.get('law','')} {it.get('paragraph','')} | {it['id']} | {it['source_file']}]\n{it['text']}"
        for it in items
    )


# -----------------------------
# Quellen / citations allowlist
# -----------------------------
_CIT_RE = re.compile(r"(?:§\s*\d+[a-z]?)\s*(?:SGB\s*(?:I{1,3}|IV|V|VI|VII|VIII|IX|X|XI|XII|II|2))", flags=re.IGNORECASE)

def _norm_citation(c: str) -> str:
    c = (c or "").strip()
    c = re.sub(r"\s+", " ", c)
    c = c.replace("SGB 2", "SGB II")
    return c.upper()

def _extract_citations(text: str) -> set:
    if not text:
        return set()
    found = set()
    t = _normalize_citation_order(text)
    for m in _CIT_RE.finditer(t):
        found.add(_norm_citation(m.group(0)))
    return found

def _allowed_citations_from_items(items) -> set:
    out = set()
    for it in items or []:
        law = (it.get("law") or "").strip()
        par = (it.get("paragraph") or "").strip()
        if not law or not par:
            continue
        par2 = par.strip() if par.strip().startswith("§") else "§ " + par.strip()
        out.add(_norm_citation(f"{par2} {law}"))
    return out

def _repair_remove_illegal_citations(text: str, illegal: List[str]) -> str:
    t = text or ""
    t = _normalize_citation_order(t)
    for cit in illegal:
        m = re.search(r"§\s*(\d+[A-Z]?)\s*SGB\s*([A-Z0-9]+)", cit, flags=re.IGNORECASE)
        if not m:
            continue
        num = m.group(1)
        book = m.group(2)
        pat = re.compile(rf"§\s*{re.escape(num)}\s*SGB\s*{re.escape(book)}", flags=re.IGNORECASE)
        t = pat.sub("", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def _repair_illegal_citations_with_ollama(text: str, items, illegal: List[str]) -> str:
    allowed = sorted(list(_allowed_citations_from_items(items)))
    prompt = f"""SYSTEM:
Du bist ein strenger Korrektur-Assistent für einen Widerspruch ans Jobcenter.
WICHTIG:
- Entferne/ersetze ALLE unzulässigen Gesetzesverweise, die NICHT in ALLOWED_CITATIONS stehen.
- Du darfst KEINE neuen §-Zitate hinzufügen.
- Du darfst KEINE neuen Fakten hinzufügen.
- Gib nur den korrigierten Brieftext zurück, ohne Kommentare.

ALLOWED_CITATIONS:
{", ".join(allowed) if allowed else "(keine)"}

ILLEGAL_FOUND:
{", ".join(illegal)}

TEXT_TO_FIX:
{text}
"""
    out = _call_ollama(prompt).strip()
    return out if out else text


# -----------------------------
# NO-STRONG-CLAIMS guard
# -----------------------------
_STRONG_PATTERNS = [
    (re.compile(r"\bführt\s+zu[r]?\s+Nichtigkeit\b", re.IGNORECASE), "absolute_nichtigkeit"),
    (re.compile(r"\bist\s+rechtswidrig\b", re.IGNORECASE), "absolute_rechtswidrig"),
    (re.compile(r"\bkeine\s+Ausnahmen\s+vorliegen\b", re.IGNORECASE), "assumes_no_exceptions"),
    (re.compile(r"\bungültig\b|\bunwirksam\b", re.IGNORECASE), "invalidity_words"),
    (re.compile(r"\bnichtig(?:keit)?\b", re.IGNORECASE), "nichtigkeit_any"),
    (re.compile(r"\bschwerwiegenden?\s+Fehler\b", re.IGNORECASE), "schwerwiegender_fehler"),
    (re.compile(r"\bbesonders\s+schwerwiegenden?\s+Fehler\b", re.IGNORECASE), "besondere_schwere"),
    (re.compile(r"\bschwerwiegend\w*\b", re.IGNORECASE), "schwerwiegend_any"),
    (re.compile(r"\boffensichtlich\b", re.IGNORECASE), "offensichtlich_word"),
    (re.compile(r"\bohne\s+Zweifel\b|\beindeutig\b|\bsicher\b", re.IGNORECASE), "certainty_words"),
    (re.compile(r"\bes\s+ist\s+klar\b", re.IGNORECASE), "it_is_clear"),
    (re.compile(r"\bfragwürdig\b", re.IGNORECASE), "fragwuerdig"),
    (re.compile(r"\bwahrscheinlich\b", re.IGNORECASE), "wahrscheinlich"),
]

def _find_strong_claims(text: str) -> List[str]:
    t = _normalize_citation_order(text or "")
    hits = []
    for rx, name in _STRONG_PATTERNS:
        if rx.search(t):
            hits.append(name)
    return hits

def _hard_soften_strong_claims(text: str) -> str:
    t = _normalize_citation_order(text or "")

    BAN_REPLACEMENTS = {
        r"\bführt\s+zu[r]?\s+Nichtigkeit\b": "kann einen Verfahrensmangel begründen",
        r"\bist\s+rechtswidrig\b": "erscheint rechtswidrig",
        r"\bkeine\s+Ausnahmen\s+vorliegen\b": "soweit keine Ausnahme eingreift",
        r"\bungültig\b|\bunwirksam\b": "verfahrensfehlerhaft",
        r"\bnichtig(?:keit)?\b": "Verfahrensmangel",
        r"\bschwerwiegenden?\s+Fehler\b": "Verfahrensmangel",
        r"\bbesonders\s+schwerwiegenden?\s+Fehler\b": "Verfahrensmangel",
        r"\bschwerwiegend\w*\b": "",
        r"\boffensichtlich\b": "",
        r"\bohne\s+Zweifel\b|\beindeutig\b|\bsicher\b": "nach Aktenlage",
        r"\bes\s+ist\s+klar\b": "nach Aktenlage",
        r"\bfragwürdig\b": "prüfungsbedürftig",
        r"\bwahrscheinlich\b": "",
    }

    for pat, repl in BAN_REPLACEMENTS.items():
        t = re.sub(pat, repl, t, flags=re.IGNORECASE)

    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def _repair_strong_claims_with_ollama(text: str, flags: List[str]) -> str:
    prompt = f"""SYSTEM:
Du bist ein strenger Korrektur-Assistent für einen Widerspruch ans Jobcenter.
WICHTIG:
- Entferne oder entschärfe ALLE zu starken/absoluten rechtlichen Schlussfolgerungen.
- Keine Formulierungen wie: "ungültig", "unwirksam", "nichtig", "Nichtigkeit", "offensichtlich", "schwerwiegend".
- Keine absoluten Aussagen / keine Erfolgsgarantien.
- Ersetze durch vorsichtige Formulierungen: "bitte prüfen", "nach Aktenlage", "es bestehen Zweifel".
- Du darfst KEINE neuen Fakten hinzufügen.
- Du darfst KEINE neuen Gesetzesverweise hinzufügen.
- Gib nur den korrigierten Brieftext zurück, ohne Kommentare.

STRONG_FLAGS:
{", ".join(flags)}

TEXT_TO_FIX:
{text}
"""
    out = _call_ollama(prompt).strip()
    return out if out else text


# -----------------------------
# Letter building
# -----------------------------
def _fmt_jobcenter_address(facts: Dict[str, Any]) -> Optional[str]:
    addr = _safe_str(facts.get("jobcenter_address"))
    plz = _safe_str(facts.get("jobcenter_postalCode") or facts.get("jobcenter_postal_code") or facts.get("jobcenter_plz"))
    city = _safe_str(facts.get("jobcenter_city"))
    parts = []
    if addr:
        parts.append(addr)
    if plz or city:
        parts.append(" ".join([p for p in [plz, city] if p]).strip())
    out = "\n".join([p for p in parts if p])
    return out if out else None

def _fmt_user_block(facts: Dict[str, Any]) -> str:
    lines = []
    name = " ".join([p for p in [_safe_str(facts.get("vorname")), _safe_str(facts.get("nachname"))] if p]).strip()
    if name:
        lines.append(name)

    kunden = _safe_str(facts.get("kunden_nummer") or facts.get("bg_nummer"))
    if kunden:
        lines.append(f"BG/Kundennummer: {kunden}")

    addr = _safe_str(facts.get("user_address"))
    plz = _safe_str(facts.get("user_postalCode") or facts.get("user_postal_code") or facts.get("user_plz"))
    city = _safe_str(facts.get("user_city"))

    if addr:
        lines.append(addr)
    if plz or (city and addr):
        line = " ".join([p for p in [plz, city] if p]).strip()
        if line:
            lines.append(line)

    return "\n".join(lines).strip()

def _fmt_jobcenter_block_strict(facts: Dict[str, Any]) -> str:
    jc_label = _safe_str(facts.get("jobcenter_label") or facts.get("jobcenter"))
    jc_addr = _fmt_jobcenter_address(facts)
    if jc_label and jc_addr:
        return f"An\n{jc_label}\n{jc_addr}".strip()
    if jc_label:
        return f"An\n{jc_label}".strip()
    if jc_addr:
        return f"An\nJobcenter\n{jc_addr}".strip()
    return "An\ndas zuständige Jobcenter"

def _fmt_date_line(facts: Dict[str, Any]) -> str:
    dt = _safe_str(facts.get("letter_date"))
    if not dt:
        dt = _fmt_de_long(date.today())
    user_city = _safe_str(facts.get("user_city"))
    if user_city:
        return f"{user_city}, den {dt}"
    return dt

def _make_anlagen_list(req_text: str, facts: Dict[str, Any]) -> List[str]:
    if bool(facts.get("no_anlagen")):
        return []
    out = ["Kopie des Bescheids"]
    extra = facts.get("anlagen")
    if isinstance(extra, list):
        for x in extra:
            s = _safe_str(x)
            s = re.sub(r"[.]+$", "", s).strip()
            if s:
                out.append(s)

    seen, uniq = set(), []
    for a in out:
        a2 = re.sub(r"[.]+$", "", (a or "")).strip()
        if not a2:
            continue
        key = a2.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(a2)
    return uniq


# -----------------------------
# Body prompt (patched)
# -----------------------------
def _widerspruch_body_prompt(context: str, facts: dict, req_text: str) -> str:
    bescheid_datum = _safe_str(facts.get("bescheid_datum"))
    zugang_datum = _safe_str(facts.get("zugang_datum"))

    return f"""SYSTEM:
Du schreibst den INHALT (Fließtext) eines formellen deutschen Widerspruchs an ein Jobcenter.

HARTE REGELN:
- Schreibe ausschließlich in zusammenhängenden Absätzen (Fließtext). KEINE Überschriften, KEINE Listen, KEINE Aufzählungszeichen, KEINE A)/B).
- Verwende NICHT die Begriffe "Kläger", "Beklagter".
- Verwende NUR Fakten aus USER_TEXT und FACTS. Keine erfundenen Details.
- Zitiere Gesetze (§) NUR, wenn sie im CONTEXT stehen. Sonst keine §-Nummern.
- KEINE starken Schlussfolgerungen: NICHT "ungültig", "unwirksam", "nichtig", "Nichtigkeit", "offensichtlich", "schwerwiegend".
- Keine Garantien. Nur neutral: "bitte prüfen", "es bestehen Zweifel", "nach Aktenlage".
- WICHTIG: Erst 1–3 Absätze zur kurzen Begründung/Prüfbitte, DANACH als letzten Absatz eine kurze Bitte (Eingangsbestätigung / ggf. Akteneinsicht / ggf. Erläuterung / erneute Entscheidung).
- Schreibe KEINEN Abschnitt "Anlagen" und erwähne "Anlagen" nicht. Anlagen werden außerhalb des Bodys eingefügt.

TOPIC GUARDS:
- Wenn USER_TEXT von "Termin" / "Meldeversäumnis" handelt: Verwende ausschließlich Termin-bezogene Formulierungen (z.B. "den Termin wahrnehmen") und NICHT "Arbeit/Job/Arbeitgeber".
- Wenn USER_TEXT "krank" + "Attest/Bescheinigung" enthält: Nenne diese Fakten kurz ("krankheitsbedingt", "ärztliche Bescheinigung liegt vor", "nicht rechtzeitig eingereicht") ohne zusätzliche erfundene Hintergründe.
- WICHTIG: In Krank+Attest+Termin-Fällen keine Standard-Passagen zur "Anhörung" oder "§ 24 SGB X" verwenden, es sei denn USER_TEXT nennt ausdrücklich "Anhörung" oder "§ 24".

FORMAT:
- 3 bis 6 Absätze, jeweils 2–4 Sätze.
- Keine Überschriften, keine Bulletpoints.

FACTS:
Bescheid-Datum: {bescheid_datum}
Zugang-Datum: {zugang_datum}

USER_TEXT:
{(req_text or "").strip()}

CONTEXT:
{(context or "").strip()}

Gib ausschließlich den Text zurück.
"""


def _compose_letter_enforced_header(facts: Dict[str, Any], req_text: str, body: str, include_anlagen: bool = True) -> str:
    user_block = _fmt_user_block(facts)
    jc_block = _fmt_jobcenter_block_strict(facts)
    date_line = _fmt_date_line(facts)

    bescheid_raw = _safe_str(facts.get("bescheid_datum"))
    bescheid_disp = _fmt_bescheid_date_display(bescheid_raw) if bescheid_raw else ""
    subject = f"Betreff: Widerspruch gegen Bescheid vom {bescheid_disp}" if bescheid_disp else "Betreff: Widerspruch"

    name = " ".join([p for p in [_safe_str(facts.get("vorname")), _safe_str(facts.get("nachname"))] if p]).strip()

    parts = []
    if user_block:
        parts.append(user_block)
        parts.append("")

    parts.append(jc_block)
    parts.append("")
    parts.append(date_line)
    parts.append("")
    parts.append(subject)
    parts.append("")
    parts.append("Sehr geehrte Damen und Herren,")
    parts.append("")
    parts.append(f"hiermit lege ich Widerspruch gegen den Bescheid{(' vom ' + bescheid_disp) if bescheid_disp else ''} ein.")
    parts.append("")
    parts.append((body or "").strip())
    parts.append("")
    parts.append("Mit freundlichen Grüßen")
    if name:
        parts.append(name)

    if include_anlagen:
        anlagen = _make_anlagen_list(req_text=req_text, facts=facts)
        if anlagen:
            parts.append("")
            parts.append("Anlagen:")
            for a in anlagen:
                aa = re.sub(r"[.]+$", "", (a or "")).strip()
                if aa:
                    parts.append(f"- {aa}")

    out = "\n".join(parts)
    out = _sanitize_widerspruch_text(out)
    out = _remove_klaeger_terms(out)
    return out.strip()


def _polish_with_ollama(base_letter: str, style: str) -> str:
    style = (style or "standard").lower().strip()
    if style == "short":
        style_hint = "Halte die Formulierungen knapp, aber ändere keine Struktur."
    elif style == "formal":
        style_hint = "Sehr formell und neutral, aber ändere keine Struktur."
    else:
        style_hint = "Neutral und gut lesbar, aber ändere keine Struktur."
    prompt = f"""SYSTEM:
Du bist ein reiner Korrektur- und Stilassistent.
WICHTIG:
- Du darfst KEINE neuen Fakten hinzufügen.
- Du darfst KEINE neuen Abschnitte hinzufügen.
- Du darfst KEINE Abschnitte entfernen.
- Du darfst KEINE neuen Gesetzesverweise hinzufügen.
- Keine Überschriften, keine Listen, keine A)/B).
- Gib ausschließlich den korrigierten Text zurück, ohne Kommentare.

STYLE:
{style_hint}

TEXT:
{base_letter}
"""
    out = _call_ollama(prompt)
    return out.strip() if out else base_letter


# -----------------------------
# Retrieve query helpers
# -----------------------------
def _is_procedural_query(q: str) -> bool:
    ql = (q or "").lower()
    return any(k in ql for k in PROC_KEYWORDS)


# -----------------------------
# Quellen post-process helpers
# -----------------------------
def _extract_title_from_text(text: str) -> str:
    t = (text or "").replace("\n", " ").strip()
    if not t:
        return ""
    m = re.search(r"\b§\s*\d+[a-z]?\b.*?\bSGB\s*X\b\s+(.+?)(?:\(\s*1\s*\)|\(\s*2\s*\)|\(\s*3\s*\)|$)", t, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip(" -:;,.")[:120]
    m2 = re.search(r"\b§\s*\d+[a-z]?\b\s+(.+?)(?:\(\s*1\s*\)|\(\s*2\s*\)|\(\s*3\s*\)|$)", t, flags=re.IGNORECASE)
    if m2:
        title = m2.group(1).strip(" -:;,.")
        title = re.sub(r"^SGB\s*X\s+", "", title, flags=re.IGNORECASE).strip()
        return title[:120]
    return ""

def _build_quellen_unique(items, max_cites: int = 8):
    best = {}
    for it in items or []:
        law = (it.get("law") or "").strip()
        par = (it.get("paragraph") or "").strip()
        if not law and not par:
            continue
        key = (law, par)
        if key not in best or float(it.get("distance", 999)) < float(best[key].get("distance", 999)):
            best[key] = it
    ranked = sorted(best.values(), key=lambda x: float(x.get("distance", 999)))
    out = []
    for it in ranked[:max_cites]:
        out.append({
            "law": it.get("law", ""),
            "paragraph": it.get("paragraph", ""),
            "title": _extract_title_from_text(it.get("text", "")),
            "source_file": it.get("source_file", ""),
            "distance": it.get("distance", None),
        })
    return out


# -----------------------------
# Generator
# -----------------------------
def _generate_widerspruch_letter(facts: Dict[str, Any], req_text: str, k: int, style: str, include_anlagen: bool):
    facts = _hydrate_jobcenter_from_db(facts or {})

    bescheid_datum = _safe_str(facts.get("bescheid_datum"))
    query = f"Widerspruch Jobcenter Bescheid {bescheid_datum}. Akteneinsicht Zustellung Verwaltungsakt Begründung Minderung Terminversäumnis. {req_text[:600]}"
    items = _retrieve(query, k=max(2, min(MAX_K, int(k or DEFAULT_K))), require_absatz=True)
    context = _build_context(items)

    body = _call_ollama(_widerspruch_body_prompt(context=context, facts=facts, req_text=req_text)).strip()
    if not body:
        raise RuntimeError("LLM returned empty body")

    body = _sanitize_widerspruch_text(body)
    body = _enforce_official_no_lists(body)

    letter = _compose_letter_enforced_header(facts=facts, req_text=req_text, body=body, include_anlagen=include_anlagen)
    letter = _sanitize_widerspruch_text(letter)

    if STRICT_CITATIONS:
        allowed = _allowed_citations_from_items(items)
        used = _extract_citations(letter)
        illegal = sorted(list(used - allowed))
        if illegal:
            for _ in range(MAX_REPAIR_ROUNDS_CIT):
                fixed = _repair_illegal_citations_with_ollama(letter, items=items, illegal=illegal)
                fixed = _sanitize_widerspruch_text(fixed)
                used2 = _extract_citations(fixed)
                illegal2 = sorted(list(used2 - allowed))
                letter = fixed
                illegal = illegal2
                if not illegal:
                    break
            if illegal:
                letter = _repair_remove_illegal_citations(letter, illegal)

    if NO_STRONG_CLAIMS:
        flags = _find_strong_claims(letter)
        if flags:
            for _ in range(MAX_REPAIR_ROUNDS_STRONG):
                fixed = _repair_strong_claims_with_ollama(letter, flags=flags)
                fixed = _sanitize_widerspruch_text(fixed)
                letter = fixed
                flags = _find_strong_claims(letter)
                if not flags:
                    break
            if flags:
                letter = _hard_soften_strong_claims(letter)

    letter = _polish_with_ollama(letter, style=style)
    letter = _sanitize_widerspruch_text(letter)
    letter = _remove_klaeger_terms(letter)

    # Split Anlagen to process body separately
    parts = letter.split("\nAnlagen:\n", 1)
    head_part = _enforce_official_no_lists(parts[0])

    # PATCH: remove Anhörung/§24 paragraph for Krank+Attest Termin cases (unless user asked)
    head_part = _guard_remove_anhörung_para_for_krank_attest(head_part, req_text=req_text)
    head_part = _sanitize_widerspruch_text(head_part)

    # Enforce final Bitte paragraph (including Aufhebung+Neuberechnung)
    head_part = _dedupe_and_fix_bitte_paragraphs(head_part, req_text=req_text)

    if len(parts) == 2:
        letter = head_part + "\n\nAnlagen:\n" + parts[1].strip()
    else:
        letter = head_part

    # PATCH: remove work/job hallucinations for Termin/Krank cases
    letter = _guard_remove_work_context_if_not_in_user_text(letter, req_text=req_text)
    letter = _sanitize_widerspruch_text(letter)

    # Re-check illegal citations after edits
    if STRICT_CITATIONS:
        allowed = _allowed_citations_from_items(items)
        used = _extract_citations(letter)
        illegal = sorted(list(used - allowed))
        if illegal:
            letter = _repair_remove_illegal_citations(letter, illegal)

    # Re-check strong claims
    if NO_STRONG_CLAIMS:
        flags = _find_strong_claims(letter)
        if flags:
            letter = _hard_soften_strong_claims(letter)

    letter = _sanitize_widerspruch_text(letter)
    letter = _remove_klaeger_terms(letter)

    return letter, items, (context if context else None)


# -----------------------------
# PDF
# -----------------------------
def _text_to_pdf_bytes(text: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    font_name = "Helvetica"
    for path in [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\calibri.ttf", r"C:\Windows\Fonts\segoeui.ttf"]:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("UIFont", path))
                font_name = "UIFont"
                break
            except Exception:
                pass

    t = (text or "").replace("**", "").replace("\r\n", "\n").replace("\r", "\n")

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    left, right, top, bottom = 50, 50, 60, 60
    font_size, leading = 11, 14
    c.setFont(font_name, font_size)
    y = height - top
    max_width = width - left - right

    def wrap_line(line: str):
        words = line.split(" ")
        out, cur = [], ""
        for w in words:
            cand = (cur + " " + w).strip()
            if pdfmetrics.stringWidth(cand, font_name, font_size) <= max_width:
                cur = cand
            else:
                if cur:
                    out.append(cur)
                cur = w
        if cur:
            out.append(cur)
        return out

    for raw in t.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            y -= leading
            if y < bottom:
                c.showPage()
                c.setFont(font_name, font_size)
                y = height - top
            continue
        for wline in wrap_line(line):
            c.drawString(left, y, wline)
            y -= leading
            if y < bottom:
                c.showPage()
                c.setFont(font_name, font_size)
                y = height - top

    c.save()
    buf.seek(0)
    return buf.getvalue()


def _make_preview(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    t = t[:PREVIEW_HARD_CAP]
    limit = max(300, int(PREVIEW_CHARS or 1400))
    if len(t) <= limit:
        return t
    cut = t[:limit]
    last_nl = cut.rfind("\n")
    last_dot = cut.rfind(".")
    best = max(last_nl, last_dot)
    if best > 200:
        cut = cut[:best + 1]
    return cut.rstrip() + "\n\n🔒 Vollständiger Text nach Freischaltung (Download)."


# -----------------------------
# Routes
# -----------------------------
@app.get("/")
def root():
    return {"service": "SGB II + SGB X RAG API", "collection": COLLECTION, "docs": "/docs", "ui": "/ui (if folder exists)"}


@app.get("/pricing")
@app.get("/pricing/")
def pricing():
    return FileResponse("ui/pricing.html")


@app.get("/impressum")
@app.get("/impressum/")
def impressum():
    return FileResponse("ui/impressum.html")


@app.get("/datenschutz")
@app.get("/datenschutz/")
def datenschutz():
    return FileResponse("ui/datenschutz.html")


@app.get("/jobcenters")
def jobcenters():
    if not os.path.exists(JOB_CENTER_JSON):
        return {"items": []}
    with open(JOB_CENTER_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = []
    if isinstance(data, list):
        for x in data:
            if not isinstance(x, dict):
                continue
            if not x.get("id") or not x.get("label"):
                continue
            items.append({
                "id": x["id"],
                "label": x["label"],
                "address": x.get("address") or "",
                "postalCode": x.get("postalCode") or "",
                "city": x.get("city") or "",
            })
    items.sort(key=lambda a: (a["label"] or "").lower())
    return {"items": items}


@app.get("/search", response_model=list[SearchHit])
def search(q: str = Query(..., min_length=2), k: int = Query(DEFAULT_K, ge=1, le=MAX_K)):
    res = col.query(query_texts=[E5_QUERY_PREFIX + q], n_results=k, include=["documents", "metadatas", "distances"])
    hits = []
    for i in range(len(res["ids"][0])):
        text = _strip_passage_prefix(res["documents"][0][i])
        md = res["metadatas"][0][i] or {}
        hits.append(SearchHit(
            id=res["ids"][0][i],
            score=float(res["distances"][0][i]),
            text=text,
            source_file=md.get("source_file", ""),
            law=md.get("law", ""),
            paragraph=md.get("paragraph", ""),
        ))
    return hits


@app.get("/rag")
def rag(q: str = Query(..., min_length=2), k: int = Query(DEFAULT_K, ge=1, le=MAX_K)):
    items = _retrieve(q, k=k, require_absatz=True)
    return {"query": q, "k": k, "items": items, "context": _build_context(items)}


@app.post("/widerspruch/validate")
def validate_widerspruch(req: ValidateRequest):
    return _validate_text(req.text)


@app.post("/widerspruch/fix")
def fix_widerspruch(req: ValidateRequest):
    fixed = _sanitize_widerspruch_text(req.text)
    fixed = _remove_klaeger_terms(fixed)
    v = _validate_text(fixed)
    return {"ok": v["ok"], "fixed_text": fixed, "validation": v}


@app.post("/widerspruch/pdf")
def widerspruch_pdf(req: PdfRequest):
    pdf_bytes = _text_to_pdf_bytes(req.text)
    fname = (req.filename or "widerspruch.pdf").strip()
    if not fname.lower().endswith(".pdf"):
        fname += ".pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )


@app.post("/widerspruch")
def widerspruch(req: WiderspruchRequest):
    facts = _hydrate_jobcenter_from_db(req.facts or {})
    k = max(1, min(MAX_K, int(req.k or DEFAULT_K)))
    style = (req.style or "standard").lower().strip()
    req_text = extract_user_text(req)

    letter, items, context = _generate_widerspruch_letter(
        facts=facts, req_text=req_text, k=k, style=style, include_anlagen=True
    )
    validation = _validate_text(letter)
    quellen = _build_quellen_unique(items, max_cites=8) if req.include_quellen else []

    return {
        "ok": bool(validation.get("ok")),
        "text": letter,
        "validation": validation,
        "quellen": quellen,
        "context": context if req.include_context else None
    }


@app.post("/widerspruch/workflow")
def widerspruch_workflow(req: WiderspruchWorkflowRequest):
    uid = (req.user_id or "").strip()
    if not uid:
        raise HTTPException(400, "Missing user_id")

    is_preview = bool(getattr(req, "preview", False))
    if not is_preview:
        _consume_use_or_402(uid)

    facts = _hydrate_jobcenter_from_db(req.facts or {})
    k = max(1, min(MAX_K, int(req.k or DEFAULT_K)))
    style = (req.style or "standard").lower().strip()
    req_text = extract_user_text(req)

    letter, items, context = _generate_widerspruch_letter(
        facts=facts, req_text=req_text, k=k, style=style, include_anlagen=True
    )

    if is_preview:
        preview_text = _make_preview(letter)
        return Response(
            content=preview_text.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"X-Preview": "1"}
        )

    validation = _validate_text(letter)
    fmt = (req.format or "json").lower().strip()

    if fmt == "txt":
        out_name = (req.filename or "widerspruch.txt").strip()
        if not out_name.lower().endswith(".txt"):
            out_name += ".txt"
        return Response(
            content=letter.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{out_name}"'}
        )

    if fmt == "pdf":
        pdf_bytes = _text_to_pdf_bytes(letter)
        out_name = (req.filename or "widerspruch.pdf").strip()
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{out_name}"'}
        )

    quellen = _build_quellen_unique(items, max_cites=8) if req.include_quellen else []
    return {
        "ok": bool(validation.get("ok")),
        "text": letter,
        "validation": validation,
        "quellen": quellen,
        "context": context if req.include_context else None
    }


# -----------------------------
# Tester endpoints
# -----------------------------
@app.post("/t/{token}/widerspruch/workflow")
def tester_widerspruch_workflow(token: str, req: WiderspruchWorkflowRequest):
    if not _tester_enabled():
        raise HTTPException(404, "Tester access not enabled")

    _tester_consume_or_403(token)
    req.preview = False

    facts = _hydrate_jobcenter_from_db(req.facts or {})
    k = max(1, min(MAX_K, int(req.k or DEFAULT_K)))
    style = (req.style or "standard").lower().strip()
    req_text = extract_user_text(req)

    letter, items, context = _generate_widerspruch_letter(
        facts=facts, req_text=req_text, k=k, style=style, include_anlagen=True
    )

    validation = _validate_text(letter)
    fmt = (req.format or "txt").lower().strip()

    if fmt == "txt":
        out_name = (req.filename or "widerspruch.txt").strip()
        if not out_name.lower().endswith(".txt"):
            out_name += ".txt"
        return Response(
            content=letter.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{out_name}"'}
        )

    if fmt == "pdf":
        pdf_bytes = _text_to_pdf_bytes(letter)
        out_name = (req.filename or "widerspruch.pdf").strip()
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{out_name}"'}
        )

    quellen = _build_quellen_unique(items, max_cites=8) if req.include_quellen else []
    return {
        "ok": bool(validation.get("ok")),
        "text": letter,
        "validation": validation,
        "quellen": quellen,
        "context": context if req.include_context else None
    }


@app.get("/tester/ui/{token}", response_class=HTMLResponse)
def ui_tester(token: str):
    if not _tester_enabled():
        raise HTTPException(404, "Tester access not enabled")

    _tester_check_or_403(token)

    html = f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Tester UI — Widerspruch</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; max-width: 980px; }}
    .row {{ display: flex; gap: 16px; flex-wrap: wrap; }}
    .col {{ flex: 1; min-width: 280px; }}
    label {{ font-weight: 600; display: block; margin: 10px 0 6px; }}
    input, textarea, select {{ width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 10px; }}
    textarea {{ min-height: 160px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    button {{ padding: 10px 14px; border-radius: 12px; border: 0; cursor: pointer; }}
    .btn {{ background: #111; color: #fff; }}
    .btn2 {{ background: #eee; }}
    .card {{ border: 1px solid #e6e6e6; border-radius: 16px; padding: 16px; margin-top: 16px; }}
    pre {{ white-space: pre-wrap; word-break: break-word; padding: 12px; border-radius: 12px; background: #fafafa; border: 1px solid #eee; }}
    .small {{ color: #666; font-size: 13px; }}
    .banner {{ background:#fff7ed; border:1px solid #fed7aa; padding:12px 14px; border-radius: 14px; }}
    .hint {{ color:#666; font-size: 12px; margin-top:6px; }}
    .inline {{ display:flex; gap:10px; align-items:center; }}
    .inline input[type="checkbox"] {{ width:auto; }}
  </style>
</head>
<body>
  <h2>Tester UI — Widerspruch (SGB II / SGB X)</h2>
  <div class="banner">
    <div><strong>Interne Testphase</strong> — Volltext wird sofort erzeugt.</div>
    <div class="small">Tipp: Jobcenter per Dropdown auswählen → Adresse wird automatisch gesetzt.</div>
  </div>

  <div class="card">
    <div class="row">
      <div class="col">
        <label>Vorname</label>
        <input id="vorname" placeholder="Max" />
      </div>
      <div class="col">
        <label>Nachname</label>
        <input id="nachname" placeholder="Mustermann" />
      </div>
      <div class="col">
        <label>Ort (user_city)</label>
        <input id="user_city" placeholder="Berlin" value="Berlin"/>
      </div>
    </div>

    <div class="row">
      <div class="col">
        <label>BG/Kundennummer</label>
        <input id="kunden_nummer" placeholder="BG-123456" />
      </div>
      <div class="col">
        <label>Bescheid-Datum</label>
        <input id="bescheid_datum" type="date" />
        <div class="hint">Wird als YYYY-MM-DD an den Server gesendet; im Brief als „01. Dezember 2025“ formatiert.</div>
      </div>
      <div class="col">
        <label>Jobcenter</label>
        <select id="jobcenter_select">
          <option value="">— Bitte auswählen —</option>
        </select>
        <div class="hint">Adresse wird aus der Jobcenter-Liste ergänzt.</div>
      </div>
    </div>

    <div class="row">
      <div class="col">
        <label>Ausgabeformat</label>
        <select id="format">
          <option value="json">JSON (Text im Feld)</option>
          <option value="txt" selected>TXT Download</option>
          <option value="pdf">PDF Download</option>
        </select>
      </div>
      <div class="col">
        <label>Stil</label>
        <select id="style">
          <option value="standard" selected>standard</option>
          <option value="formal">formal</option>
          <option value="short">short</option>
        </select>
      </div>
      <div class="col"></div>
    </div>

    <label>Bescheid-Text / Input</label>
    <textarea id="bescheid_text" placeholder="Hier den Bescheidtext einfügen..."></textarea>

    <div class="card" style="margin-top:14px;">
      <h3 style="margin:0 0 8px 0;">Anlagen</h3>
      <div class="inline">
        <input id="no_anlagen" type="checkbox" />
        <label for="no_anlagen" style="margin:0;">Keine Anlagen (auch keine Kopie des Bescheids)</label>
      </div>
      <div class="hint">Optional: Eine Anlage pro Zeile. Wenn leer, wird standardmäßig „Kopie des Bescheids“ eingefügt (außer Checkbox ist aktiv).</div>
      <textarea id="anlagen" placeholder="(optional) Anlage 1&#10;Anlage 2"></textarea>
    </div>

    <div style="margin-top:12px; display:flex; gap:10px; align-items:center;">
      <button class="btn" id="btn">Generate</button>
      <button class="btn2" id="btnFill">Demo-Facts</button>
      <span class="small" id="status"></span>
    </div>
  </div>

  <div class="card">
    <h3>Result</h3>
    <pre id="out">—</pre>
  </div>

<script>
const TOKEN = "{_escape_html(token)}";

function parseAnlagenLines() {{
  const raw = document.getElementById("anlagen").value || "";
  const lines = raw.split(/\\r?\\n/).map(s => s.trim()).filter(Boolean);
  const seen = new Set();
  const out = [];
  for (const l of lines) {{
    const k = l.toLowerCase();
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(l);
  }}
  return out;
}}

function buildPayload() {{
  const jcSel = document.getElementById("jobcenter_select");
  const jcId = (jcSel.value || "").trim();
  const jcLabel = jcSel.options[jcSel.selectedIndex]?.text || "";

  const facts = {{
    vorname: document.getElementById("vorname").value || "",
    nachname: document.getElementById("nachname").value || "",
    user_city: document.getElementById("user_city").value || "",
    kunden_nummer: document.getElementById("kunden_nummer").value || "",
    bescheid_datum: (document.getElementById("bescheid_datum").value || "").trim(),
    jobcenter_id: jcId,
    jobcenter_label: jcLabel && jcId ? jcLabel : "",
    bescheid_text: document.getElementById("bescheid_text").value || ""
  }};

  const noAnlagen = document.getElementById("no_anlagen").checked;
  if (noAnlagen) {{
    facts.no_anlagen = true;
  }} else {{
    const anlagen = parseAnlagenLines();
    if (anlagen.length) facts.anlagen = anlagen;
  }}

  const format = document.getElementById("format").value;
  const style = document.getElementById("style").value;

  return {{
    facts,
    text: facts.bescheid_text,
    k: 3,
    format,
    style,
    preview: false
  }};
}}

async function run() {{
  const status = document.getElementById("status");
  const out = document.getElementById("out");
  status.textContent = "Generating...";
  out.textContent = "—";

  const payload = buildPayload();
  const format = payload.format;

  try {{
    const url = `/t/${{encodeURIComponent(TOKEN)}}/widerspruch/workflow`;
    const res = await fetch(url, {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify(payload)
    }});

    if (!res.ok) {{
      const txt = await res.text();
      throw new Error(txt || `HTTP ${{res.status}}`);
    }}

    if (format === "txt" || format === "pdf") {{
      const blob = await res.blob();
      const a = document.createElement("a");
      const ext = format === "pdf" ? "pdf" : "txt";
      a.href = URL.createObjectURL(blob);
      a.download = `widerspruch.${{ext}}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      out.textContent = `Download gestartet: widerspruch.${{ext}}`;
    }} else {{
      const data = await res.json();
      out.textContent = data.text || JSON.stringify(data, null, 2);
    }}

    status.textContent = "Done";
  }} catch (e) {{
    status.textContent = "Error";
    out.textContent = String(e);
  }}
}}

async function loadJobcenters() {{
  try {{
    const res = await fetch("/jobcenters");
    if (!res.ok) return;
    const data = await res.json();
    const items = (data.items || []);
    const sel = document.getElementById("jobcenter_select");
    while (sel.options.length > 1) sel.remove(1);
    for (const jc of items) {{
      const opt = document.createElement("option");
      opt.value = jc.id;
      opt.textContent = jc.label;
      sel.appendChild(opt);
    }}
  }} catch (_) {{}}
}}

document.getElementById("btn").addEventListener("click", run);

document.getElementById("btnFill").addEventListener("click", () => {{
  document.getElementById("vorname").value = "Broke";
  document.getElementById("nachname").value = "Smoke";
  document.getElementById("user_city").value = "Berlin";
  document.getElementById("kunden_nummer").value = "BG-745342";
  document.getElementById("bescheid_datum").value = "2025-11-20";
  document.getElementById("bescheid_text").value =
`Ich lege Widerspruch gegen den Bescheid ein. Kürzung 10% wegen nicht Erscheinen zum Termin am 01.11.2025. Ich war krank. Ärztliches Attest liegt vor, wurde aber versehentlich nicht rechtzeitig eingereicht.`;
  document.getElementById("no_anlagen").checked = false;
  document.getElementById("anlagen").value = "Ärztliches Attest";
}});

loadJobcenters();
</script>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.post("/tester/mint")
def tester_mint(request: Request, email: str, days: int = TESTER_TTL_DAYS, max_uses: int = TESTER_MAX_USES):
    if not _tester_enabled():
        raise HTTPException(400, "TESTER_SECRET is not set")

    if not ADMIN_SECRET:
        raise HTTPException(403, "ADMIN_SECRET is not set")

    admin = (request.headers.get("X-Admin-Secret") or request.query_params.get("admin") or "").strip()
    if admin != ADMIN_SECRET:
        raise HTTPException(403, "Forbidden")

    token = _mint_tester_token(email=email, days=days)
    tid = _token_id(token)

    db = _load_testers()
    rec = db.get(tid) or {}
    rec.update({"uses": int(rec.get("uses") or 0), "max_uses": int(max_uses)})
    db[tid] = rec
    _save_testers(db)

    return {
        "token": token,
        "ui_url": f"{APP_URL}/tester/ui/{token}",
        "workflow_url": f"{APP_URL}/t/{token}/widerspruch/workflow",
        "token_id": tid,
        "days": int(days),
        "max_uses": int(max_uses),
    }


# --- Stripe endpoints (optional) ---
@app.post("/billing/checkout")
def billing_checkout(req: CheckoutRequest):
    _require_stripe_config()
    price_id = _stripe_price_id()
    success_url = f"{APP_URL}/ui/?paid=1&user_id={req.user_id}"
    cancel_url = f"{APP_URL}/ui/?canceled=1&user_id={req.user_id}"
    days = max(1, min(int(req.days or 7), 365))
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": req.user_id, "days": str(days), "mode": STRIPE_MODE},
    )
    return {"url": session.url, "id": session.id}


@app.post("/billing/webhook")
async def stripe_webhook(request: Request):
    _require_stripe_config()
    payload = await request.body()

    sig_header = (request.headers.get("Stripe-Signature") or request.headers.get("stripe-signature") or "")
    whsec = _stripe_webhook_secret()

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, whsec)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")
    except Exception as e:
        raise HTTPException(400, f"Webhook parse error: {e}")

    event_id = event.get("id", "")
    event_type = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}

    try:
        if _dedup_event(event_id):
            return {"ok": True, "dedup": True}
    except Exception as e:
        print("Dedup store error:", repr(e))

    try:
        if event_type == "checkout.session.completed":
            metadata = obj.get("metadata") or {}
            user_id = (metadata.get("user_id") or "").strip()
            days = max(1, min(int((metadata.get("days") or "7").strip() or "7"), 365))
            customer_id = obj.get("customer") or ""
            session_id = obj.get("id") or ""
            payment_intent_id = obj.get("payment_intent") or ""
            charge_id = ""
            if payment_intent_id:
                pi = stripe.PaymentIntent.retrieve(payment_intent_id)
                charge_id = pi.get("latest_charge") or ""
            if user_id:
                _set_user_access(
                    user_id=user_id,
                    days=days,
                    stripe_customer_id=customer_id,
                    session_id=session_id,
                    charge_id=charge_id,
                    payment_intent_id=payment_intent_id
                )

        elif event_type == "charge.refunded":
            charge_id = obj.get("id") or ""
            user_id = _find_user_by_charge(charge_id)
            if user_id:
                _revoke_access(user_id=user_id)

    except Exception as e:
        print("Webhook handler error:", repr(e), "event_type:", event_type)

    return {"ok": True}


@app.get("/me")
def me(user_id: str):
    db = _load_subs()
    rec = db.get(user_id) or {}
    until = rec.get("access_until")
    active = _is_user_paid(user_id)
    uses_left = int(rec.get("uses_left") or 0)
    return {"user_id": user_id, "active": active, "access_until": until, "uses_left": uses_left, "mode": STRIPE_MODE}


@app.get("/health")
def health():
    return {"ok": True, "collection": COLLECTION, "chunks": col.count()}


@app.exception_handler(Exception)
async def all_exception_handler(request: Request, exc: Exception):
    print("=== EXCEPTION ===")
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": str(exc)})
