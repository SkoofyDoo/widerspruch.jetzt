"""LEGACY ingest — do not extend.

Use ``app.rag.v2.ingest_v2`` instead:
``uv run python -m app.rag.v2.ingest_v2``
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from dotenv import load_dotenv

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document

from app.rag.v2.chroma_store import open_collection
from app.rag.v2.ingest_config import (
    ABSATZ_SPLIT,
    CLEANED_DIR,
    CLEANED_GLOB,
    ChunkMeta,
    EMBED_BATCH_SIZE,
    MAX_CHARS_ONE_CHUNK,
    NORMS_JSONL,
)
from app.rag.v2.rebuild_flag import read_rebuild_flag, write_rebuild_flag

load_dotenv()

print("=" * 70)
print("RAG WITH LANGCHAIN  [LEGACY — prefer app.rag.v2.ingest_v2]")
print("=" * 70)


def load_documents_from_norms(path: Path) -> list[Document]:
    """One Document per § from structured GII XML parse (norms.jsonl)."""
    docs: list[Document] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            source_file = row.get("source_file") or f"{row.get('law_key', 'law')}.txt"
            docs.append(
                Document(
                    page_content=(row.get("text") or "").strip(),
                    metadata={
                        "source": str(path),
                        "source_file": source_file,
                        "law": row.get("law", "UNKNOWN"),
                        "paragraph": row.get("paragraph", ""),
                        "title": row.get("title", ""),
                        "absätze": row.get("absätze") or [],
                    },
                )
            )
    return docs


def load_documents_from_cleaned() -> list[Document]:
    loader = DirectoryLoader(
        path=str(CLEANED_DIR),
        glob=str(CLEANED_GLOB),
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    )
    return loader.load()


def load_documents() -> list[Document]:
    if NORMS_JSONL.is_file():
        docs = load_documents_from_norms(NORMS_JSONL)
        print(f"[TEXT LOADER]: norms.jsonl → {len(docs)} paragraphs")
        return docs
    docs = load_documents_from_cleaned()
    print(f"[TEXT LOADER]: cleaned/ → {len(docs)} documents")
    return docs


def extract_absatz(chunk_text: str) -> str:
    m = re.search(r"\((\d+[a-z]?)\)", chunk_text)
    return f"({m.group(1)})" if m else ""


def chunk_from_norm(doc: Document) -> list[Document]:
    """Prefer structured absätze from XML; fall back to regex split."""
    text = doc.page_content.strip()
    law = doc.metadata.get("law") or "UNKNOWN"
    paragraph = doc.metadata.get("paragraph") or ""
    source_file = doc.metadata.get("source_file") or Path(doc.metadata.get("source", "unknown")).name
    title = doc.metadata.get("title") or ""
    header = f"{paragraph} {title}".strip() if title else paragraph

    structured = doc.metadata.get("absätze") or []
    if structured:
        chunks: list[Document] = []
        for item in structured:
            label = (item.get("label") or "").strip()
            body = (item.get("text") or "").strip()
            if not body and not label:
                continue
            content = f"{header}\n{label} {body}".strip() if label else f"{header}\n{body}".strip()
            chunks.append(
                Document(
                    page_content=content,
                    metadata={
                        "source": doc.metadata.get("source", ""),
                        "source_file": source_file,
                        "law": law,
                        "paragraph": paragraph,
                        "absatz": label,
                    },
                )
            )
        if chunks:
            return chunks

    # Legacy path / missing absätze list
    base = ChunkMeta.from_document(source_file, text)
    if law != "UNKNOWN":
        base.law = law
    if paragraph:
        base.paragraph = paragraph

    if len(text) <= MAX_CHARS_ONE_CHUNK:
        md = base.as_dict()
        md["absatz"] = ""
        return [Document(page_content=text, metadata=md)]

    parts = ABSATZ_SPLIT.split(text)
    head = parts[0].strip()
    body_parts = [p.strip() for p in parts[1:] if p.strip()]
    if not body_parts:
        return [Document(page_content=text, metadata=base.as_dict())]

    out: list[Document] = []
    for p in body_parts:
        content = f"{head}\n{p}" if head else p
        md = base.as_dict()
        md["absatz"] = extract_absatz(p)
        out.append(Document(page_content=content, metadata=md))
    return out


def chunking(documents: list[Document]) -> list[Document]:
    chunks: list[Document] = []
    for doc in documents:
        # norms.jsonl docs already carry law/paragraph
        if "absätze" in doc.metadata or doc.metadata.get("paragraph"):
            chunks.extend(chunk_from_norm(doc))
            continue

        text = doc.page_content.strip()
        base = ChunkMeta.from_document(doc.metadata["source"], text)
        if len(text) <= MAX_CHARS_ONE_CHUNK:
            md = base.as_dict()
            md["absatz"] = ""
            chunks.append(Document(page_content=text, metadata=md))
            continue

        parts = ABSATZ_SPLIT.split(text)
        header = parts[0].strip()
        body = [p.strip() for p in parts[1:] if p.strip()]
        if not body:
            chunks.append(Document(page_content=text, metadata=base.as_dict()))
            continue

        for p in body:
            content = f"{header}\n{p}" if header else p
            md = base.as_dict()
            md["absatz"] = extract_absatz(p)
            chunks.append(Document(page_content=content, metadata=md))

    print(f"[CHUNKING]: Länge der Chunks {len(chunks)}")
    if chunks:
        print(chunks[0].metadata)
    return chunks


def add_chunks(collection, chunks):
    """Chunks und Metadata zur Collection hinzufügen"""
    ids = [f"{c.metadata['source_file']}::{i}" for i, c in enumerate(chunks)]
    print(f"[CHROMA]: indexing {len(ids)} chunks, batch={EMBED_BATCH_SIZE}", flush=True)
    texts = [c.page_content for c in chunks]
    metas = [
        {
            "source_file": c.metadata["source_file"],
            "law": c.metadata["law"],
            "paragraph": c.metadata["paragraph"],
            "absatz": c.metadata["absatz"],
        }
        for c in chunks
    ]

    for start in range(0, len(ids), EMBED_BATCH_SIZE):
        end = start + EMBED_BATCH_SIZE
        collection.add(
            ids=ids[start:end],
            documents=texts[start:end],
            metadatas=metas[start:end],
        )
        print(f"[CHROMA]: Embedded: {end}/{len(ids)}")

    print(collection.count() == len(chunks))
    return


def main():
    documents = load_documents()
    if not documents:
        raise RuntimeError(
            "No corpus loaded. Run: python -m app.parser.fetch_xml && python -m app.parser.parse_xml"
        )

    chunks = chunking(documents)

    rebuild = read_rebuild_flag()
    collection = open_collection(rebuild=rebuild)
    if rebuild or collection.count() == 0:
        add_chunks(collection, chunks)
        write_rebuild_flag(False)
    else:
        print(
            "[CHROMA]: skip embed (rebuild flag is false — "
            "re-run parse_xml after corpus changes)"
        )

    query = (
        "Instruct: Given a question about German social law (SGB II / SGB X), "
        "retrieve the most relevant legal paragraph.\n"
        "Query: Wann ist eine Arbeit unzumutbar?"
    )

    result = collection.query(query_texts=[query], n_results=3)

    for doc, meta, dist in zip(
        result["documents"][0],
        result["metadatas"][0],
        result["distances"][0],
    ):
        print(dist, meta)
        print(doc[:400])
        print("---")


if __name__ == "__main__":
    main()
