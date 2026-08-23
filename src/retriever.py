from __future__ import annotations


import os
from dotenv import load_dotenv

from chroma_store import get_client

load_dotenv()






if __name__ == "__main__":
    print("=" * 70)
    print("RETRIEVER")
    print("=" * 70)
    get_client()