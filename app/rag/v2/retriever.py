from __future__ import annotations
 
from dotenv import load_dotenv
from app.rag.v2.chroma_store import open_collection
from rank_bm25 import BM25Okapi


load_dotenv()


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
            "distance": float(dists[i]),
        })
    return items



def build_bm25(collection) -> list[dict]:
    corpus = collection.get(include = ["documents", "metadatas"])
    ids = corpus["ids"]
    docs = corpus["documents"]
    metas = corpus["metadatas"]
    
    tokenized_corpus = [d.lower().split() for d in docs]
    bm25 = BM25Okapi(tokenized_corpus)   
     
    return bm25, ids, docs, metas

def sparse_search(bm25, ids, docs, metas, question: str, n: int) -> list[dict]:
    scores = bm25.get_scores(question.lower().split())
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
            "score": float(scores[i])
        })
    return items

def rrf_fuse(dense_items: list[dict], sparce_items: list[dict], rrf_k: int = 60) -> list[dict]:
    scores = {}
    payload = {}
    
    for rank, it in enumerate(dense_items, start = 1):
        i = it["id"]
        scores[i] = scores.get(i, 0.0) + 1.0 / (rrf_k + rank)
        payload[i] = it
        
    for rank, it in enumerate(sparce_items, start = 1):
        i = it["id"]
        scores[i] = scores.get(i, 0.0) + 1.0 / (rrf_k + rank)
        payload[i] = it
        
    ordered = sorted(scores.keys(), key = lambda i: scores[i], reverse = True)
    out = []
    for i in ordered:
        row = dict(payload[i])
        row["rrf_score"] = scores[i]
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