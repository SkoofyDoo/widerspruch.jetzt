"""Ingest v2: norms.jsonl → Absatz chunks → LangChain Chroma.

Source of truth for text is the XML pipeline (fetch_xml → parse_xml → norms.jsonl).
This module only indexes; it does not fetch HTML or parse XML.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.v2.chroma_store import get_client
from app.rag.v2.ingest_config import (
    CHROMA_DIR,
    COLLECTION_METADATA,
    COLLECTION_NAME,
    EMBED_BATCH_SIZE,
    EMBEDDING_MODEL,
    EMBEDDINGS_BASE_URL,
    MAX_CHARS_ONE_CHUNK,
    NORMS_JSONL,
)
from app.rag.v2.rebuild_flag import read_rebuild_flag, write_rebuild_flag

load_dotenv()

# Secondary split only when a single Absatz is still too long for embedding.
_FALLBACK_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=MAX_CHARS_ONE_CHUNK,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
    length_function=len,
)

_SLUG_RE = re.compile(r"[^\w\-]+", re.UNICODE)


def load_norms(path: Path = NORMS_JSONL) -> list[dict]:
    """Load structured paragraphs from XML parse output."""
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {path}. Run: python -m app.parser.fetch_xml && "
            "python -m app.parser.parse_xml"
        )
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    print(f"[LOAD]: {path.name} → {len(rows)} paragraphs")
    return rows


def _header(row: dict) -> str:
    paragraph = (row.get("paragraph") or "").strip()
    title = (row.get("title") or "").strip()
    return f"{paragraph} {title}".strip() if title else paragraph


def _chunk_id(meta: dict, index: int) -> str:
    """Stable id for Chroma (rebuild-friendly)."""
    law = _SLUG_RE.sub("_", (meta.get("law") or "law").lower())
    paragraph = _SLUG_RE.sub("_", (meta.get("paragraph") or "p").lower())
    absatz = _SLUG_RE.sub("_", (meta.get("absatz") or "x").lower()) or "x"
    return f"{law}::{paragraph}::{absatz}::{index}"


def norm_to_absatz_docs(row: dict) -> list[Document]:
    """One Document per Absatz; page_content keeps § header for retrieval context."""
    header = _header(row)
    law = row.get("law") or "UNKNOWN"
    paragraph = row.get("paragraph") or ""
    source_xml = row.get("source_xml") or ""
    source_file = row.get("source_file") or f"{row.get('law_key', 'law')}.txt"
    base_meta = {
        "law": law,
        "paragraph": paragraph,
        "title": row.get("title") or "",
        "source_xml": source_xml,
        "source_file": source_file,
        "source": str(NORMS_JSONL),
    }

    structured = row.get("absätze") or []
    docs: list[Document] = []

    if structured:
        for item in structured:
            label = (item.get("label") or "").strip()
            body = (item.get("text") or "").strip()
            if not body and not label:
                continue
            if label:
                content = f"{header}\n{label} {body}".strip()
            else:
                content = f"{header}\n{body}".strip()
            docs.append(
                Document(
                    page_content=content,
                    metadata={**base_meta, "absatz": label},
                )
            )
        if docs:
            return docs

    # Fallback: ganzes § als ein Dokument wenn Absätzeliste leer ist 
    text = (row.get("text") or "").strip()
    if not text:
        return []
    return [Document(page_content=text, metadata={**base_meta, "absatz": ""})]


def split_if_too_long(docs: list[Document]) -> list[Document]:
    """Keep Absatz boundaries; only split oversized Absätze further."""
    out: list[Document] = []
    for doc in docs:
        if len(doc.page_content) <= MAX_CHARS_ONE_CHUNK:
            out.append(doc)
            continue
        parts = _FALLBACK_SPLITTER.split_documents([doc])
        print(
            f"[SPLIT]: {doc.metadata.get('law')} {doc.metadata.get('paragraph')} "
            f"{doc.metadata.get('absatz')} → {len(parts)} sub-chunks"
        )
        out.extend(parts)
    return out


def build_chunks(rows: list[dict]) -> list[Document]:
    chunks: list[Document] = []
    for row in rows:
        chunks.extend(norm_to_absatz_docs(row))
    chunks = split_if_too_long(chunks)
    print(f"[CHUNK]: {len(chunks)} chunks")
    return chunks


def get_embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=EMBEDDINGS_BASE_URL)


def open_vectorstore(rebuild: bool) -> Chroma:
    """LangChain Chroma wrapper over the shared persist dir / collection."""
    client = get_client()
    if rebuild:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"[CHROMA]: deleted collection {COLLECTION_NAME}")
        except Exception:
            pass

    return Chroma(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        collection_metadata=COLLECTION_METADATA,
    )


def add_chunks(store: Chroma, chunks: list[Document]) -> None:
    ids = [_chunk_id(c.metadata, i) for i, c in enumerate(chunks)]
    print(f"[CHROMA]: indexing {len(ids)} chunks, batch={EMBED_BATCH_SIZE}")
    for start in range(0, len(ids), EMBED_BATCH_SIZE):
        end = start + EMBED_BATCH_SIZE
        store.add_documents(documents=chunks[start:end], ids=ids[start:end])
        print(f"[CHROMA]: embedded {min(end, len(ids))}/{len(ids)}")


def smoke_query(store: Chroma, n_results: int = 3) -> None:
    query = (
        "Instruct: Given a question about German social law (SGB II / SGB X), "
        "retrieve the most relevant legal paragraph.\n"
        "Query: Wann ist eine Arbeit unzumutbar?"
    )
    hits = store.similarity_search_with_score(query, k=n_results)
    print("[SMOKE]:")
    for doc, score in hits:
        meta = doc.metadata
        print(score, meta.get("law"), meta.get("paragraph"), meta.get("absatz"))
        print(doc.page_content[:400])
        print("---")


def main() -> None:
    rebuild = read_rebuild_flag()
    print("=" * 70)
    print("INGEST V2  (norms.jsonl → Absatz → LangChain Chroma)")
    print(f"CHROMA_DIR={CHROMA_DIR}")
    print(f"COLLECTION={COLLECTION_NAME}  REBUILD={str(rebuild).lower()}")
    print("=" * 70)

    rows = load_norms()
    chunks = build_chunks(rows)
    if not chunks:
        raise RuntimeError("No chunks built from norms.jsonl")

    store = open_vectorstore(rebuild=rebuild)
    existing = store._collection.count()  # langchain_chroma Collection handle
    if rebuild or existing == 0:
        add_chunks(store, chunks)
        write_rebuild_flag(False)
    else:
        print(
            f"[CHROMA]: collection has {existing} items; "
            "skip embed (rebuild flag is false — re-run parse_xml after corpus changes)"
        )

    smoke_query(store)


if __name__ == "__main__":
    main()
