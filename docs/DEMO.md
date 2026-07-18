# Demo guide (5–8 minutes)

This guide is for recruiters, reviewers, and you recording a short Loom/video.

## Option A — No LLM (structure only)

1. Open the repository and skim `README.md` + `docs/ARCHITECTURE.md`.
2. Open `samples/letter_example.txt` (illustrative formal letter).
3. Open `app/generation/pipeline.py` and walk the safety stages.
4. Run unit tests:

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Option B — Full local demo (recommended)

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) with model `qwen2.5:14b-instruct` (or set `OLLAMA_MODEL`)
- Built Chroma index under `data/chroma` (see README quickstart)

### Steps

```bash
# 1) install
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate
pip install -r requirements.txt

# 2) env
copy .env.example .env   # Windows
# cp .env.example .env   # Unix

# 3) run API
uvicorn app.main:app --host 127.0.0.1 --port 8008
```

Then:

```powershell
# Windows
.\scripts\demo_curl.ps1
```

```bash
# Unix
bash scripts/demo_curl.sh
```

Or open the UI: http://127.0.0.1:8008/ui/

### UI walkthrough script

1. Fill name, BG number (10 digits), Jobcenter, dates.
2. Paste a short case description (illness + missed appointment + reduction).
3. Click **preview** → show truncated draft + disclaimer.
4. Explain paywall: preview free, download consumes credit / tester token.
5. Show `/docs` OpenAPI briefly.
6. Show `GET /health` → `chroma_ok`, `chunks`, `ollama_ok`.

## Screencast checklist (90–180 seconds)

1. README one-liner + architecture diagram (5s)
2. UI form fill (20s)
3. Preview letter (20s)
4. Highlight citation / Amtsstil in output (15s)
5. Code jump: `pipeline.py` stages (20s)
6. `pytest` green (10s)
7. Docker one-liner or `docker compose config` (10s)
8. Closing: “document assistance, not legal advice” (5s)

Add the Loom link to README when ready:

```markdown
**Demo video:** https://...
```

## Talking points (interview)

- How do citation allowlists prevent invented § references?
- Why soften “strong claims” in a legal-adjacent product?
- Why preview must not burn credits?
- What would you change for multi-instance production storage?
