# Offline corpus pipeline

Official **XML** from [gesetze-im-internet.de](https://www.gesetze-im-internet.de/hinweise.html) (preferred).

```bash
# from repo root (widerspruch.jetzt/)
python -m app.parser.fetch_xml
python -m app.parser.parse_xml
# or one shot:
python scripts/update_corpus.py

# then embed (separate, longer step):
uv run python -m app.rag.v2.ingest_v2   # rebuilds when data/chroma_rebuild.flag is true
```

| Script / service | Role |
| ---------------- | ---- |
| `fetch_xml.py` | Download SGB II / SGB X / SGG XML ZIPs → `data/raw_xml/` |
| `parse_xml.py` | Parse norms → `data/norms.jsonl` + `data/cleaned/sg*.txt` |
| `scripts/update_corpus.py` | fetch + parse (skip parse if XML unchanged) |
| `corpus-cron` (compose profile) | Weekly Monday 03:00 Europe/Berlin |

`ingest` prefers `data/norms.jsonl` when present (structured `law` / `paragraph` / `absätze`). Otherwise it falls back to `data/cleaned/`.

## Weekly cron on VPS (Docker Compose)

```bash
# api + weekly corpus refresh
docker compose --profile cron up --build -d

# first deploy: also refresh immediately
CORPUS_CRON_RUN_ON_START=true docker compose --profile cron up -d

# manual run anytime
docker compose --profile cron run --rm --entrypoint python corpus-cron /app/scripts/update_corpus.py
```

Schedule lives in `scripts/corpus.crontab` (`0 3 * * 1`).  
Job updates **norms/cleaned only** — it does **not** rebuild Chroma.
`parse_xml` sets `data/chroma_rebuild.flag` to `true` when paragraphs were added/removed/changed.
Then re-embed:

```bash
uv run python -m app.rag.v2.ingest_v2
```

Successful ingest writes the flag back to `false`.

## Legacy HTML path

Still available if you need it:

```bash
python app/parser/fetch_law.py
python app/parser/clean.py
```

| Script         | Role                                      |
| -------------- | ----------------------------------------- |
| `fetch_law.py` | Download HTML Einzelnormen                |
| `clean.py`     | Extract text from HTML (fragile)          |

## Data flow

```text
gii xml.zip  (weekly cron / manual)
   → data/raw_xml/{sgb2,sgbx,sgg}/*.xml
   → data/norms.jsonl
   → Chroma (app.rag.v2.ingest_v2, on demand when chroma_rebuild.flag is true)
```
