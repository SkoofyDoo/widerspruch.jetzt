from __future__ import annotations
 
from dotenv import load_dotenv
# from langchain_core.documents import Document
# from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from chroma_store import open_collection
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


if __name__ == "__main__":
    print("=" * 70)
    print("RETRIEVER")
    print("=" * 70)
    
    collection = open_collection(rebuild = False)
    print("Collection Count:", collection.count())
    
    dense_items = dense_search(
        collection, 
        question = "Wann ist eine arbeit unzumutbar?", 
        n = 5)
    
    for d in dense_items:
        print("---")
        print(d["distance"], d["law"], d["paragraph"], d["absatz"])
        print(d["text"][:300])
        print("---")
    
    
    bm25, ids, docs, metas = build_bm25(collection)
    sparce_items = sparse_search(bm25, ids, docs, metas, question = "Wann ist eine arbeit unzumutbar?", n = 5)
    
    for s in sparce_items:
            print("---")
            print(s["score"], s["law"], s["paragraph"], s["absatz"])
            print(s["text"][:300])
            print("---")