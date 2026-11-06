# Architecture

## Overview

WIDERSPRUCH.JETZT is a **modular monolith**: one FastAPI process, clear domain packages.

```text
Browser UI (vanilla JS)
        │
        ▼
   FastAPI (app/main.py)
        │
        ├─ routes/          HTTP adapters (thin)
        ├─ generation/      prompts + guards + pipeline
        ├─ rag/             retrieve + citation allowlist
        ├─ billing/         Stripe + credit store

        ├─ pdf/             A4 export
        └─ feedback/        SMTP
        │
        ▼
 Chroma (SGB II/X chunks)  +  Ollama (local LLM)
```

## Offline index pipeline

```text
gesetze-im-internet.de  (official XML ZIPs)
   │  app/parser/fetch_xml.py
   ▼
data/raw_xml/{sgb2,sgbx,sgg}/*.xml
   │  app/parser/parse_xml.py
   ▼
data/norms.jsonl  (+ data/cleaned/sg*.txt for legacy)
   │  app/rag/v2/ingest.py
   ▼
data/chroma  collection wdjetzt
```

Legacy HTML path (`fetch_law.py` / `clean.py`) remains available but is not preferred.

On VPS, compose profile `cron` runs `corpus-cron` (supercronic) weekly: `scripts/update_corpus.py` → refresh `norms.jsonl` / `cleaned/` without rebuilding Chroma.

## Online letter pipeline (safety-first)

```text
User facts + free text
   │
   ▼
1. Build retrieval query (domain keywords + user snippet)
   │
   ▼
2. Vector search (E5 query: prefix)
   │  procedural bias → prefer SGB X first
   │  distance cutoff + Absatz quality filter
   ▼
3. LLM body generation (Ollama) with strict prompt rules
   │
   ▼
4. Deterministic composition (header, greeting, Anlagen)
   │
   ▼
5. Post-guards
   │  • sanitize phrasing
   │  • no bullet lists (Amtsstil)
   │  • citation allowlist (only retrieved §)
   │  • soften strong legal claims
   │  • topic guards (Krank/Attest/Arbeit)
   │  • enforced “Ich bitte um …” paragraph
   ▼
6. Preview + download (open portfolio) OR paywall when enabled
```

## Why these choices

| Choice | Rationale |
|--------|-----------|
| Local Ollama | No third-party LLM data exfiltration for sensitive cases; cheap demos |
| Citation allowlist | Grounding: model may not invent § that were not retrieved |
| JSON credit store | Fast to ship; honest limitation for multi-instance production |
| Modular monolith | Clear domains without microservice ops tax |
| Vanilla UI | Zero build step; product focus over SPA complexity |

## Billing state (paid path)

```text
checkout.session.completed
   → set_user_access(user_id, days)  # +1 credit
preview=1
   → generate, do NOT consume
download=1
   → consume_use_or_402 then generate/export
charge.refunded
   → revoke_access
```

## Package map

| Package | Responsibility |
|---------|----------------|
| `app/config.py` | Env config |
| `app/rag/` | Retrieval + citations |
| `app/generation/` | Prompts, guards, pipeline |
| `app/billing/` | Credits + Stripe |

| `app/routes/` | HTTP surface (workflow, search, billing, pages) |
| `src/` | Offline corpus pipeline only (fetch → index) |
