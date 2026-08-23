from __future__ import annotations
import os
import re
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
CLEANED_DIR = DATA_DIR / "cleaned"
CHROMA_DIR = DATA_DIR / "chroma"

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen3-embedding:4b")
EMBEDDINGS_BASE_URL = os.getenv("EMBEDDINGS_BASE_URL", "http://127.0.0.1:11434")

MAX_CHARS_ONE_CHUNK = 2000
ABSATZ_SPLIT = re.compile(r"\n(?=\(\d+[a-z]?\))")
CLEANED_GLOB = "sgb*.txt"



REBUILD = True
EMBED_BATCH_SIZE = 32

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
        
        
       
        


    