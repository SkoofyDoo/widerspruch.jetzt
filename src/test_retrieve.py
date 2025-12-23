import os
os.environ["ANONYMIZED_TELEMETRY"] = "FALSE"
os.environ["CHROMA_TELEMETRY"] = "FALSE"

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

CHROMA_DIR = "data/chroma"
COLLECTION = "laws_de"

def main():
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    embed_fn = SentenceTransformerEmbeddingFunction(model_name="intfloat/multilingual-e5-base")
    col = client.get_collection(name=COLLECTION, embedding_function=embed_fn)

    q = "Akteneinsicht"
    res = col.query(
        query_texts=["query: " + q],
        n_results=6,
        include=["metadatas", "documents", "distances"]  # <-- ids тут НЕ указывать
    )

    # ids Chroma возвращает отдельно, без include
    ids = res.get("ids", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    docs = res.get("documents", [[]])[0]
    dists = res.get("distances", [[]])[0]

    for i in range(min(6, len(docs))):
        md = metas[i] if i < len(metas) else {}
        doc = docs[i].replace("passage:", "", 1).strip()
        cid = ids[i] if i < len(ids) else "N/A"
        dist = dists[i] if i < len(dists) else None

        print(md.get("law"), md.get("paragraph"), md.get("source_file"))
        print("  id:", cid, "| dist:", dist)
        print("  snippet:", doc[:160].replace("\n", " "), "\n")

if __name__ == "__main__":
    main()
