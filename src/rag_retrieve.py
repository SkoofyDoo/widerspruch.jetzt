from rag_store import get_collection

PROC_KEYWORDS = [
  "bescheid","widerspruch","anhörung","akteneinsicht","frist","zustellung",
  "verwaltungsakt","begründung","formfehler","verfahrensfehler","überprüfung",
  "rücknahme","widerruf","sozialgericht","eilantrag","aufschiebende wirkung",
  "wiedereinsetzung"
]

def is_procedural(q: str) -> bool:
    ql = (q or "").lower()
    return any(k in ql for k in PROC_KEYWORDS)

def retrieve(query: str, k: int = 10):
    col = get_collection()

    procedural = is_procedural(query)

    results = []
    seen = set()

    # 1) если процедурный вопрос — сначала SGB X
    if procedural:
        r1 = col.query(
            query_texts=["query: " + query],
            n_results=max(k, 12),
            where={"law": "SGB X"},
            include=["documents","metadatas","distances"]
        )
        for doc, md, dist in zip(r1["documents"][0], r1["metadatas"][0], r1["distances"][0]):
            key = (md.get("law",""), md.get("paragraph",""), md.get("source_file",""), doc[:120])
            if key in seen: 
                continue
            seen.add(key)
            results.append({"text": doc.replace("passage:","",1).strip(), "meta": md, "distance": dist})

    # 2) добираем из общего корпуса
    need = k - len(results)
    if need > 0:
        r2 = col.query(
            query_texts=["query: " + query],
            n_results=max(need * 2, need),
            include=["documents","metadatas","distances"]
        )
        for doc, md, dist in zip(r2["documents"][0], r2["metadatas"][0], r2["distances"][0]):
            key = (md.get("law",""), md.get("paragraph",""), md.get("source_file",""), doc[:120])
            if key in seen:
                continue
            seen.add(key)
            results.append({"text": doc.replace("passage:","",1).strip(), "meta": md, "distance": dist})
            if len(results) >= k:
                break

    return results
