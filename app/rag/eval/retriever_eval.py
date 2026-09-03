"""
Offline hit@3 eval: legacy (e5 / laws_de) vs hybrid v2 (Qwen / wdjetzt + BM25 + RRF).

Run from repo root:
  uv run python evals/retrieval/retriever_eval.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

# New stack reads Qwen settings from env / chroma_store defaults
from app.rag.v2.chroma_store import open_collection  # noqa: E402
from app.rag.v2.retriever import build_bm25, dense_search, rrf_fuse, sparse_search  # noqa: E402

QUERIES_PATH = Path(__file__).resolve().parent / "queries.jsonl"
TOP_K = 3
DENSE_N = 30
SPARSE_N = 30

# Legacy index was built with e5 — must not use Qwen model from .env
LEGACY_EMBEDDING_MODEL = "intfloat/multilingual-e5-base"


def load_cases(path: Path) -> list[dict]:
    cases: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def norm_paragraph(p: str) -> str:
    return (p or "").lower().replace("§", "").strip()


def is_hit(
    items: list[dict],
    expect_paragraphs: list[str],
    expect_law: str | None = None,
    require_law: bool = False,
) -> bool:
    wanted = {norm_paragraph(x) for x in expect_paragraphs}
    for it in items:
        if require_law and expect_law and (it.get("law") or "") != expect_law:
            continue
        if norm_paragraph(it.get("paragraph", "")) in wanted:
            return True
    return False


def format_got(items: list[dict]) -> str:
    parts = []
    for it in items:
        law = it.get("law") or "?"
        par = it.get("paragraph") or "?"
        parts.append(f"{law} {par}")
    return ", ".join(parts) if parts else "(empty)"


def hybrid_top(collection, bm25_pack, question: str) -> list[dict]:
    bm25, ids, docs, metas = bm25_pack
    dense = dense_search(collection, question, n=DENSE_N)
    sparse = sparse_search(bm25, ids, docs, metas, question, n=SPARSE_N)
    return rrf_fuse(dense, sparse)[:TOP_K]


def load_legacy_retrieve():
    """Import legacy retrieve with embedding settings that match laws_de."""
    os.environ["EMBEDDING_PROVIDER"] = "local"
    os.environ["EMBEDDING_MODEL"] = LEGACY_EMBEDDING_MODEL
    os.environ["CHROMA_COLLECTION"] = "laws_de"

    import app.config as config
    import app.deps as deps

    config.EMBEDDING_PROVIDER = "local"
    config.EMBEDDING_MODEL = LEGACY_EMBEDDING_MODEL
    config.COLLECTION = "laws_de"
    deps._client = None
    deps._col = None
    deps._init_error = None

    from app.rag.v1.retrieve import retrieve

    return retrieve


def main() -> None:
    cases = load_cases(QUERIES_PATH)
    print(f"Loaded {len(cases)} cases from {QUERIES_PATH}")

    # --- new ---
    collection = open_collection(rebuild=False)
    print(f"[new] collection=wdjetzt count={collection.count()}")
    if collection.count() == 0:
        raise RuntimeError("Collection wdjetzt is empty. Run ingest with REBUILD=True first.")
    bm25_pack = build_bm25(collection)

    # --- old ---
    print(f"[old] loading legacy retrieve (laws_de + {LEGACY_EMBEDDING_MODEL})...")
    legacy_retrieve = load_legacy_retrieve()
    try:
        # warm / verify collection
        from app.deps import get_collection

        legacy_col = get_collection()
        print(f"[old] collection=laws_de count={legacy_col.count()}")
    except Exception as e:
        print(f"[old] FAILED to open laws_de: {e}")
        print("Skip old comparison; running new only.")
        legacy_retrieve = None

    new_hits = 0
    old_hits = 0
    old_ran = 0

    print("-" * 78)
    for case in cases:
        q = case["question"]
        expect = case.get("expect_paragraphs") or [case["expect_paragraph"]]
        cid = case["id"]

        fused = hybrid_top(collection, bm25_pack, q)
        new_ok = is_hit(fused, expect, expect_law=case.get("expect_law"), require_law=False)
        new_hits += int(new_ok)

        old_ok = None
        old_got = "(skipped)"
        if legacy_retrieve is not None:
            try:
                old_items = legacy_retrieve(q, k=TOP_K, require_absatz=True)
                old_ok = is_hit(old_items, expect, expect_law=case.get("expect_law"), require_law=False)
                old_hits += int(old_ok)
                old_ran += 1
                old_got = format_got(old_items)
            except Exception as e:
                old_got = f"ERROR: {e}"

        new_s = "HIT " if new_ok else "MISS"
        old_s = "HIT " if old_ok else ("MISS" if old_ok is False else "N/A ")
        print(f"{cid} new={new_s} old={old_s} | expect {expect}")
        print(f"     new: {format_got(fused)}")
        print(f"     old: {old_got}")

    total = len(cases)
    print("-" * 78)
    print(f"[new] hit@{TOP_K} = {new_hits}/{total} = {new_hits / total:.2f}")
    if old_ran:
        print(f"[old] hit@{TOP_K} = {old_hits}/{old_ran} = {old_hits / old_ran:.2f}")
        print(f"[delta] new - old = {new_hits / total - old_hits / old_ran:+.2f}")
    else:
        print("[old] no results (collection/embeddings unavailable)")


if __name__ == "__main__":
    main()
