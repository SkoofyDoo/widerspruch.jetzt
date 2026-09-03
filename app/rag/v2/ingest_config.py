from __future__ import annotations
import os
import re
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# app/rag/v2/ingest_config.py → repo root is parents[3]
ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
CLEANED_DIR = DATA_DIR / "cleaned"
# Prefer explicit env, else project-root data/chroma (single source of truth)
_chroma_env = (os.getenv("CHROMA_DIR") or "").strip().strip('"').strip("'")
CHROMA_DIR = Path(_chroma_env or (DATA_DIR / "chroma")).expanduser().resolve()

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen3-embedding:4b")
EMBEDDINGS_BASE_URL = os.getenv("EMBEDDINGS_BASE_URL", "http://127.0.0.1:11434")

MAX_CHARS_ONE_CHUNK = 2000
ABSATZ_SPLIT = re.compile(r"\n(?=\(\d+[a-z]?\))")
CLEANED_GLOB = "sg*.txt"

COLLECTION_NAME = os.getenv("INGEST_COLLECTION", "wdjetzt")
COLLECTION_METADATA = {"hnsw:space": "cosine"}

REBUILD = os.getenv("INGEST_REBUILD", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
EMBED_BATCH_SIZE = int(os.getenv("INGEST_BATCH_SIZE", "32"))

@dataclass
class ChunkMeta:
    source: str
    source_file: str
    law: str
    paragraph: str
    absatz: str

    @classmethod
    def from_document(cls, source: str, text: str) -> "ChunkMeta":
        source_file = Path(source).name
        name = source_file.lower()
        
        if name.startswith("sgb2__"):
            law = "SGB II"
        elif name.startswith("sgbx__"):
            law = "SGB X"
        elif name.startswith("sgg__"):
            law = "SGG"
        else:
            law = "UNKNOWN"
        
        paragraph = ""
        m = re.search(r"^§\s*(\d+[a-z]?)", text.strip(), re.I | re.M)
        if m:
            paragraph = f"§ {m.group(1)}"
        else:
            if name.startswith("sgb2__"):
                m = re.search(r"^sgb2__(\d+[a-z]?)_", source_file, re.I)
            elif name.startswith("sgbx__"):
                m = re.search(r"__SGBX_(\d+[a-z]?)_", source_file, re.I)
            else:
                m = None
            if m:
                paragraph = f"§ {m.group(1)}"
                
        absatz = ""
        m = re.search(r"\((\d+[a-z]?)\)", text)
        absatz = f"({m.group(1)})" if m else ""
            
            
        return cls(
            source = source,
            source_file = source_file,
            law = law,
            paragraph = paragraph,
            absatz = absatz,
        )
    
    
    
    
    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "source_file": self.source_file,
            "law": self.law,
            "paragraph": self.paragraph,
            "absatz": self.absatz,
        }
        
        
       
        


    