# Retrieval-Eval (Hybrid RAG v2)

Offline-Bewertung des lokalen Retrievers (Chroma + Qwen3-Embedding + BM25 + RRF) für WIDERSPRUCH.JETZT.

## Korpus & Index

| Komponente | Wert |
|---|---|
| Gesetze | SGB II, SGB X, SGG |
| Collection | `wdjetzt` |
| Embeddings | `qwen3-embedding:4b` (Ollama), Query mit Instruct-Prefix |
| Chunking | kurze §§ ganz; lange nach Absätzen `(1)/(2)/(3)` |
| Hybrid | Dense (Chroma) + Sparse (`rank-bm25`) + RRF (`k=60`) |

Vergleich zur Legacy-Pipeline (`laws_de` + multilingual-e5, nur dense, fixed-size Chunks): dort lagen manuelle Stichproben oft bei ca. **2–3/5** korrekten Paragraphen.

## Metrik

**Hit@3:** mindestens einer der Top-3-Chunks hat einen `paragraph` aus `expect_paragraphs` (normalisiert, z. B. `§ 10` / `10`).

`expect_law` wird aktuell nicht streng erzwungen (Metadata-Qualität), ist aber in den Cases hinterlegt.

## Ergebnis (aktuell)

### New vs Legacy (gleicher Case-Satz, n=15)

| Pipeline | Index | Retrieval | Hit@3 |
|---|---|---|---|
| **New (v2)** | `wdjetzt` (SGB II / X / SGG) | Qwen3-Embedding 4B + BM25 + RRF | **15/15 = 1.00** |
| **Legacy (v1)** | `laws_de` | multilingual-e5-base, nur dense | **3/15 = 0.20** |
| **Delta** | | | **+0.80** |

Legacy-Hits lagen vor allem bei klaren SGB-X-Verfahrensfragen (Akteneinsicht § 25, Verwaltungsakt § 31, Anhörung § 24).  
SGG-Fälle (Widerspruchsfrist, aufschiebende Wirkung, Revision) und die meisten SGB-II-Materiefälle waren bei Legacy MISS — oft fehlende/`?`-Paragraph-Metadata oder falsche Nachbarparagraphen (z. B. Frist → SGB X § 111 statt SGG § 84).

### Hinweise zur New-Pipeline

- q13 zunächst als „Was ist ein Verwaltungsakt?“ → MISS (Nachbarparagraphen).  
  Nach Formulierung **„Was ist die Definition eines Verwaltungsaktes?“** → HIT (`SGB X § 31`).
- Widerspruchsfrist / Revision brauchen SGG im Index.

## Cases

Datei: [`queries.jsonl`](./queries.jsonl) (15 Fragen).

Felder je Zeile:

- `id`, `question`
- `expect_law`, `expect_paragraph`
- `expect_paragraphs` (erlaubte Treffer, z. B. `§ 31` / `§ 31a` / `§ 31b`)
- `notes`

## Eval ausführen

Voraussetzungen:

- Ollama läuft (für New / Qwen)
- Collection `wdjetzt` befüllt
- Collection `laws_de` + lokales `sentence-transformers` / e5 (für Legacy-Vergleich)

```bash
# Repo-Root
uv run python evals/retrieval/retriever_eval.py
```

Der Lauf:

1. wertet **New** (Dense n=30 + BM25 n=30 + RRF, Top-3)
2. wertet **Legacy** (`app.rag.retrieve.retrieve`, k=3) mit Embedding-Modell fest auf `intfloat/multilingual-e5-base` (passend zu `laws_de`)
3. druckt pro Case HIT/MISS und die gefundenen Paragraphen

## App-Integration

In `.env`:

```bash
RETRIEVER_BACKEND=hybrid   # or legacy
```

`app/generation/pipeline.py` calls `app.rag.retrieve.retrieve`, which dispatches to hybrid (`wdjetzt`) or legacy (`laws_de`).

## Nächste Schritte

- End-to-end Brief mit `RETRIEVER_BACKEND=hybrid` manuell prüfen.
- Bei Bedarf Query-Rewriting für sehr generische „Was ist …?“-Fragen.
- Optional: strengeres Scoring mit `require_law=True`.
