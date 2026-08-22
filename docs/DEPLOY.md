# Deploy & demo runbook

## Status checklist (portfolio)

| Item | You do |
|------|--------|
| Code showcase | already in repo |
| HF token | https://huggingface.co/settings/tokens |
| Local DEMO preview | steps below |
| Public host | Railway (recommended) |
| Live demo link in README | after deploy |
| Loom video | optional but recommended |

## What you need

1. **Prebuilt Chroma index** in `data/chroma` (~10MB if already built)
2. **HuggingFace token** — https://huggingface.co/settings/tokens
3. Docker (optional) + account on **Railway** — https://railway.app

## A) Local demo with HuggingFace (no Ollama)

```bash
# 1) .env
copy .env.example .env   # Windows
# set:
#   LLM_PROVIDER=huggingface
#   HF_TOKEN=hf_...
#   DEMO_MODE=true
#   DEMO_ALLOW_DOWNLOAD=false

# 2) index must exist
# data/chroma  <- run src/fetch_* + clean + chunk + index once

# 3) run
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8008
```

Open http://127.0.0.1:8008/ui/ → fill form → **Vorschau**.

## B) Docker demo profile

```bash
# .env must contain HF_TOKEN=
docker compose --profile demo up --build
```

This sets `LLM_PROVIDER=huggingface` and `DEMO_MODE=true`.

## C) Docker + local Ollama (quality)

```bash
# host: ollama serve && ollama pull qwen2.5:14b-instruct
# .env: LLM_PROVIDER=ollama  DEMO_MODE=false
docker compose up --build
```

## D) Public URL for recruiters

Docker alone is not public. Pick one host:

| Host | Notes |
|------|--------|
| Railway / Render / Fly.io | Deploy Dockerfile, set env vars, attach volume or bake index |
| Hetzner VPS | Most stable for DE portfolio (~€4/mo) |
| HF Spaces (Docker) | Possible but heavy (torch + chroma) |

Minimum env on host:

```env
LLM_PROVIDER=huggingface
HF_TOKEN=...
DEMO_MODE=true
DEMO_ALLOW_DOWNLOAD=false
APP_URL=https://your-demo-host
```

Ship `data/chroma` via volume or image layer.

Then put in README:

```markdown
**Live demo:** https://your-demo-host/ui/
```

## Why Vorschau showed "Fehler" on Railway (diagnosed)

From production logs:

| Request | Result |
|---------|--------|
| `GET /`, `/ui`, `/live`, `/config` | **200** |
| `GET /health` | **502** after ~9s (`connection closed unexpectedly`) |
| `POST /widerspruch/workflow` | **502** after ~9s — same crash |

Cause: first RAG call loads **sentence-transformers/torch** → process dies on Hobby **1GB RAM**. UI only shows generic **Fehler**.

Fix shipped in code:

1. **Remote HF embeddings** (`EMBEDDING_PROVIDER=huggingface`) — no local torch  
2. **Prebuilt `data/chroma` + `jobcenter_de.json` in Docker image**  
3. Lighter runtime image (`uv sync --frozen --no-dev`) without sentence-transformers  

After push + redeploy, Vorschau should reach HF LLM without OOM.

## Railway 502 "Application failed to respond"

This is almost always **port mismatch**, **OOM on embedding load**, or the process died.

1. **Deploy Logs** must end with:
   `Starting uvicorn on 0.0.0.0:XXXX` and `Application startup complete`
2. **Settings → Networking**
   - Generate Domain
   - **Target port** = same number as `XXXX` in the log (Railway often sets this via `PORT` env)
3. **Variables**
   - Do **not** hardcode a wrong `PORT` (delete custom `PORT` and redeploy so Railway injects it)
   - Keep `HF_TOKEN`, `DEMO_MODE=true`, `LLM_PROVIDER=huggingface`
4. Open only:
   - `https://YOUR.up.railway.app/live`  → must return `{"ok":true,"live":true}`
   - then `/ui/`
5. If `/live` works but `/health` is slow/fails: missing `data/chroma` or OOM loading embeddings (upgrade RAM or mount index).

## Checklist before sharing with recruiters

- [ ] `/health` → `chroma_ok: true`, `llm_ok: true`, `demo_mode: true`
- [ ] Preview works without payment
- [ ] Download disabled or clearly limited
- [ ] Banner visible: no legal advice
- [ ] Rate limit does not 500 the app
- [ ] Sample letter link in README as fallback

## Your personal action list (order)

1. Create HF token → put in `.env`
2. Ensure `data/chroma` exists (Desktop already has it)
3. Run `DEMO_MODE=true` + HF locally once
4. `docker compose --profile demo up --build`
5. Deploy public host (Railway/Fly/VPS)
6. Paste Live Demo URL into README
7. Record 90s Loom if cold start is slow
