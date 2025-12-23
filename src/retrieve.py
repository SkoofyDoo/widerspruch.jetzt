import os
os.environ["ANONYMIZED_TELEMETRY"] = "FALSE"
os.environ["CHROMA_TELEMETRY"] = "FALSE"

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

CHROMA_DIR = "data/chroma"
COLLECTION = "laws_de"

PROC_KEYWORDS = [
    "widerspruch", "bescheid", "anhörung", "akteneinsicht", "frist", "zustellung",
    "verwaltungsakt", "begründung", "verfahrensfehler", "rücknahme", "widerruf",
    "überprüfung", "sozialgericht", "eilantrag", "aufschiebende wirkung",
    "wiedereinsetzung"
]

def is_procedural_query(q: str) -> bool:
    ql = (q or "").lower()
    return any(k in ql for k in PROC_KEYWORDS)

def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    embed_fn = SentenceTransformerEmbeddingFunction(model_name="intfloat/multilingual-e5-base")
    return client.get_collection(name=COLLECTION, embedding_function=embed_fn)

def retrieve(query: str, k: int = 8):
    col = get_collection()

    procedural = is_procedural_query(query)

    # 1) сначала SGB X, если запрос процедурный
    results = []
    seen = set()

    if procedural:
        r1 = col.query(
            query_texts=["query: " + query],
            n_results=max(6, k),
            where={"law": "SGB X"},
            include=["documents", "metadatas", "distances"]
        )
        for doc, md, dist in zip(r1["documents"][0], r1["metadatas"][0], r1["distances"][0]):
            rid = (md.get("source_file",""), md.get("paragraph",""), doc[:80])
            if rid in seen: 
                continue
            seen.add(rid)
            results.append({"text": doc.replace("passage:", "", 1).strip(), "meta": md, "distance": dist})

    # 2) добираем из общего корпуса (или только SGB II, если хочешь жёстко)
    need = k - len(results)
    if need > 0:
        r2 = col.query(
            query_texts=["query: " + query],
            n_results=max(need * 2, need),
            include=["documents", "metadatas", "distances"]
        )
        for doc, md, dist in zip(r2["documents"][0], r2["metadatas"][0], r2["distances"][0]):
            rid = (md.get("source_file",""), md.get("paragraph",""), doc[:80])
            if rid in seen:
                continue
            seen.add(rid)
            results.append({"text": doc.replace("passage:", "", 1).strip(), "meta": md, "distance": dist})
            # после получения результатов
            uniq = []
            seen = set()

            for hit in results:
                md = hit["meta"]
                key = (md.get("law",""), md.get("paragraph",""), md.get("source_file",""))
                if key in seen:
                    continue
                seen.add(key)
                uniq.append(hit)

            results = uniq[:k]

            if len(results) >= k:
                break

    return results
