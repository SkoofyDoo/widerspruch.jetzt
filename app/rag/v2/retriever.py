from __future__ import annotations

import re

from dotenv import load_dotenv
from rank_bm25 import BM25Okapi

from app.rag.v2.chroma_store import open_collection

load_dotenv()

# Split on non-letters so "Widerspruch?" / "beachten?" match corpus tokens.
_TOKEN_RE = re.compile(r"[^\w]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.split((text or "").lower()) if t]


def dense_search(collection, question: str, n: int) -> list[dict] :
    query = (
        "Instruct: Given a question about german social law (SGB II / SGB X),"
        "retrieve the most relevant paragraph. \n"
        f"Query: {question}" 
    )
    result = collection.query(
        query_texts = [query],
        n_results = n,
        include = ["documents", "metadatas", "distances"]
    )
    
    items = []
    ids = result["ids"][0]
    docs = result["documents"][0]
    metas = result["metadatas"][0]
    dists = result["distances"][0]
    
    for i in range(len(docs)):
        meta = metas[i] or {}
        items.append({
            "id": ids[i],
            "text": docs[i],
            "law": meta.get("law", ""),
            "paragraph": meta.get("paragraph", ""),
            "absatz": meta.get("absatz", ""),
            "source_file": meta.get("source_file", ""),
            "source_url": meta.get("source_url", ""),
            "distance": float(dists[i]),
        })
    return items



def build_bm25(collection) -> list[dict]:
    corpus = collection.get(include = ["documents", "metadatas"])
    ids = corpus["ids"]
    docs = corpus["documents"]
    metas = corpus["metadatas"]

    tokenized_corpus = [tokenize(d) for d in docs]
    bm25 = BM25Okapi(tokenized_corpus)

    return bm25, ids, docs, metas

def sparse_search(bm25, ids, docs, metas, question: str, n: int) -> list[dict]:
    scores = bm25.get_scores(tokenize(question))
    top_idx = sorted(range(len(scores)), key = lambda i: scores[i], reverse = True)[:n]
    items = []
    for i in top_idx:
        meta = metas[i] or {}
        items.append({
            "id": ids[i],
            "text": docs[i],
            "law": meta.get("law", " "), 
            "paragraph": meta.get("paragraph", " "), 
            "absatz": meta.get("absatz", " "), 
            "source_file": meta.get("source_file", " "), 
            "source_url": meta.get("source_url", ""),
            "score": float(scores[i])
        })
    return items

def _paragraph_key(it: dict) -> str:
    """Fuse by law+§ so multiple Absätze of the same norm reinforce each other."""
    law = (it.get("law") or "").strip()
    paragraph = (it.get("paragraph") or "").strip()
    if law or paragraph:
        return f"{law}::{paragraph}"
    return it.get("id") or ""


def _paragraph_ranks(items: list[dict]) -> dict[str, int]:
    """Map law::§ → 1-based rank (first / best chunk only)."""
    ranks: dict[str, int] = {}
    for it in items:
        key = _paragraph_key(it)
        if key and key not in ranks:
            ranks[key] = len(ranks) + 1
    return ranks


def rrf_fuse(
    dense_items: list[dict],
    sparce_items: list[dict],
    rrf_k: int = 60,
    dense_weight: float = 2.0,
    sparse_weight: float = 0.25,
) -> list[dict]:
    """Dense-primary RRF at paragraph level.

    Candidates come from dense hits; sparse only lightly boosts those §§
    (tie-break). Full sparse weight let BM25 neighbors bury dense rank-1
    hits after Absatz chunking.
    """
    dense_ranks = _paragraph_ranks(dense_items)
    sparse_ranks = _paragraph_ranks(sparce_items)

    payload: dict[str, dict] = {}
    for it in dense_items:
        key = _paragraph_key(it)
        if key and key not in payload:
            payload[key] = it

    scores: dict[str, float] = {}
    for key, rank in dense_ranks.items():
        scores[key] = dense_weight / (rrf_k + rank)
        if key in sparse_ranks:
            scores[key] += sparse_weight / (rrf_k + sparse_ranks[key])

    ordered = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    out = []
    for key in ordered:
        row = dict(payload[key])
        row["rrf_score"] = scores[key]
        out.append(row)
    return out

if __name__ == "__main__":
    print("=" * 70)
    print("RETRIEVER")
    print("=" * 70)
    
    collection = open_collection(rebuild = False)
    print("Collection Count:", collection.count())
    
    dense_items = dense_search(
        collection, 
        question = "Wie lange dauert die widerspruchsfrist?", 
        n = 3)
    
    for d in dense_items:
        print("=======DENSE======")
        print(d["distance"], d["law"], d["paragraph"], d["absatz"])
        print(d["text"][:300])
        print("---")
    
    
    bm25, ids, docs, metas = build_bm25(collection)
    sparce_items = sparse_search(bm25, ids, docs, metas, question = "Wie lange dauert die Widerspruchsfrist?", n = 3)
    
    for s in sparce_items:
            print("=======SPARCE======")
            print(s["score"], s["law"], s["paragraph"], s["absatz"])
            print(s["text"][:300])
            print("---")
            
    rrf_scores = rrf_fuse(dense_items, sparce_items, rrf_k = 60)
    
    for r in rrf_scores:
        print("=======RRF======")
        print(r["rrf_score"],r["law"], r["paragraph"], r["absatz"])
        print(r["text"][:300])
        print("---")