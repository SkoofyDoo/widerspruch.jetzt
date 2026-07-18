# Offline corpus pipeline

Build the Chroma index used by the API:

```bash
python src/fetch_sgb2.py
python src/fetch_sgbx.py
python src/clean.py
python src/chunk.py
python src/index.py
```

| Script | Role |
|--------|------|
| `fetch_sgb2.py` / `fetch_sgbx.py` | Download HTML from gesetze-im-internet.de |
| `clean.py` | Extract main text, drop site chrome |
| `chunk.py` | Fixed-size chunks + law metadata |
| `index.py` | Embed with `intfloat/multilingual-e5-base` into `data/chroma` |

Runtime retrieval lives in `app/rag/` (API source of truth).
