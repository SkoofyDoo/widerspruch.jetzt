import os
os.environ["ANONYMIZED_TELEMETRY"] = "FALSE"
os.environ["CHROMA_TELEMETRY"] = "FALSE"

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

CHROMA_DIR = "data/chroma"
COLLECTION = "laws_de"

_client = None
_col = None

def get_collection():
    global _client, _col
    if _col is not None:
        return _col

    _client = chromadb.PersistentClient(path=CHROMA_DIR)
    embed_fn = SentenceTransformerEmbeddingFunction(model_name="intfloat/multilingual-e5-base")
    _col = _client.get_collection(name=COLLECTION, embedding_function=embed_fn)
    return _col
