import os
import re
import json

IN_DIR = os.path.join("data", "cleaned")
OUT = os.path.join("data", "chunks.jsonl")

# параметры чанков
CHUNK_CHARS = 1200
OVERLAP_CHARS = 200


def guess_law_and_paragraph(filename: str):
    """
    filename пример после clean:
      sgb2__...txt
      sgbx__001__SGBX_1_....txt
    """
    low = filename.lower()
    law = "UNKNOWN"
    paragraph = ""

    if low.startswith("sgb2__"):
        law = "SGB II"
    elif low.startswith("sgbx__"):
        law = "SGB X"
        m = re.search(r"__SGBX_(\d+)_", filename)
        if m:
            paragraph = f"§ {int(m.group(1))}"

    return law, paragraph


def split_into_chunks(text: str, chunk_chars: int, overlap: int):
    text = text.strip()
    if len(text) <= chunk_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_chars)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def main():
    files = [f for f in os.listdir(IN_DIR) if f.endswith(".txt")]
    if not files:
        raise RuntimeError("Нет cleaned txt. Сначала запусти clean.py")

    total = 0
    with open(OUT, "w", encoding="utf-8") as out:
        for fn in sorted(files):
            path = os.path.join(IN_DIR, fn)
            with open(path, "r", encoding="utf-8") as f:
                text = f.read().strip()

            if not text:
                continue

            law, paragraph = guess_law_and_paragraph(fn)

            chunks = split_into_chunks(text, CHUNK_CHARS, OVERLAP_CHARS)
            for i, ch in enumerate(chunks):
                rec = {
                    "id": f"{fn}::chunk{i:04d}",
                    "text": ch,
                    "source_file": fn,
                    "law": law,
                    "paragraph": paragraph,
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                total += 1

    print("Wrote chunks:", total, "->", OUT)


if __name__ == "__main__":
    main()
