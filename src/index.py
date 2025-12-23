import os
os.environ["ANONYMIZED_TELEMETRY"] = "FALSE"
os.environ["CHROMA_TELEMETRY"] = "FALSE"

import json
import hashlib
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

CHUNKS = os.path.join("data", "chunks.jsonl")
CHROMA_DIR = os.path.join("data", "chroma")
COLLECTION = "laws_de"

def fp(rec):
    # fingerprint по смыслу: law+paragraph+text
    law = rec.get("law","")
    par = rec.get("paragraph","")
    text = rec.get("text","")
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return f"{law}|{par}|{h}"

def main():
    if not os.path.exists(CHUNKS):
        raise RuntimeError("Нет chunks.jsonl. Сначала запусти chunk.py")

    os.makedirs(CHROMA_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    embed_fn = SentenceTransformerEmbeddingFunction(model_name="intfloat/multilingual-e5-base")

    # ЖЁСТКО пересоздаём коллекцию
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass

    col = client.create_collection(
        name=COLLECTION,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )

    ids, docs, metas = [], [], []
    seen = set()
    skipped = 0

    with open(CHUNKS, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)

            key = fp(rec)
            if key in seen:
                skipped += 1
                continue
            seen.add(key)

            ids.append(rec["id"])
            docs.append("passage:" + rec["text"])
            metas.append({
                "source_file": rec.get("source_file", ""),
                "law": rec.get("law", ""),
                "paragraph": rec.get("paragraph", "")
            })

            if len(ids) >= 200:
                col.add(ids=ids, documents=docs, metadatas=metas)
                ids, docs, metas = [], [], []

    if ids:
        col.add(ids=ids, documents=docs, metadatas=metas)

    print("Indexed:", col.count(), "chunks into", COLLECTION)
    print("Skipped duplicates at index-time:", skipped)

if __name__ == "__main__":
    main()
