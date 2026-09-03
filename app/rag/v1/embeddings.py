"""
Embedding backends for Chroma.

- local: sentence-transformers (dev / index build; needs torch, heavy RAM)
- huggingface: remote feature-extraction (Railway demo; no local torch)

Index must be built with the same model id (intfloat/multilingual-e5-base).
"""

from __future__ import annotations

from typing import List

import requests

from app import config


class HuggingFaceEmbeddingFunction:
    """
    Chroma-compatible embedding function using HF Inference feature extraction.
    Avoids loading torch in the API container (critical for ~1GB Railway hobby).
    """

    def __init__(self, model_name: str | None = None, token: str | None = None):
        self.model_name = model_name or config.EMBEDDING_MODEL
        self.token = (token if token is not None else config.HF_TOKEN) or ""
        # HF router feature-extraction for sentence embeddings
        self.api_url = (
            config.HF_EMBED_API_URL
            or f"https://router.huggingface.co/hf-inference/models/{self.model_name}/pipeline/feature-extraction"
        )
        self._fallback_urls = [
            self.api_url,
            f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self.model_name}",
            f"https://api-inference.huggingface.co/models/{self.model_name}",
        ]

    def name(self) -> str:
        return f"hf-{self.model_name}"

    def __call__(self, input: List[str]) -> List[List[float]]:
        if not self.token:
            raise RuntimeError(
                "HF_TOKEN required for EMBEDDING_PROVIDER=huggingface "
                "(create fine-grained token with Inference Providers permission)."
            )
        texts = list(input or [])
        if not texts:
            return []

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        out: List[List[float]] = []
        batch_size = 8
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            payload = {"inputs": batch, "options": {"wait_for_model": True}}
            data = None
            last_err = None
            for url in self._fallback_urls:
                r = requests.post(url, headers=headers, json=payload, timeout=config.HF_TIMEOUT)
                if r.status_code == 403:
                    raise RuntimeError(
                        "HF embeddings 403: token needs Inference Providers permission. "
                        "https://huggingface.co/settings/tokens/new?ownUserPermissions=inference.serverless.write&tokenType=fineGrained"
                    )
                if r.status_code >= 400:
                    last_err = f"HF embeddings HTTP {r.status_code} @ {url}: {r.text[:200]}"
                    continue
                try:
                    data = r.json()
                    break
                except Exception as e:
                    last_err = str(e)
                    continue
            if data is None:
                raise RuntimeError(last_err or "HF embeddings failed")
            vectors = _normalize_feature_output(data, expected=len(batch))
            out.extend(vectors)
        return out


def _normalize_feature_output(data, expected: int) -> List[List[float]]:
    """
    HF may return:
      - list of vectors
      - nested token embeddings that need mean-pool
      - single vector for one input
    """
    if data is None:
        raise RuntimeError("Empty embedding response from HuggingFace")

    # Single string input sometimes returns one vector
    if isinstance(data, list) and data and isinstance(data[0], (int, float)):
        return [list(map(float, data))]

    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected embedding JSON type: {type(data)}")

    vectors: List[List[float]] = []
    for item in data:
        if isinstance(item, list) and item and isinstance(item[0], (int, float)):
            vectors.append([float(x) for x in item])
        elif isinstance(item, list) and item and isinstance(item[0], list):
            # token-level embeddings → mean pool
            dim = len(item[0])
            acc = [0.0] * dim
            n = 0
            for tok in item:
                if not tok:
                    continue
                for j, v in enumerate(tok):
                    acc[j] += float(v)
                n += 1
            if n == 0:
                raise RuntimeError("Empty token embeddings")
            vectors.append([v / n for v in acc])
        else:
            raise RuntimeError(f"Unexpected embedding item shape: {type(item)}")

    if expected and len(vectors) != expected:
        # Some endpoints collapse batch of 1 oddly
        if expected == 1 and len(vectors) > 1:
            # already mean-pooled per token list mistakenly — take first
            return [vectors[0]]
        if len(vectors) != expected:
            raise RuntimeError(f"Expected {expected} embeddings, got {len(vectors)}")
    return vectors


def get_embedding_function():
    """Return Chroma embedding function for current EMBEDDING_PROVIDER."""
    provider = (config.EMBEDDING_PROVIDER or "auto").strip().lower()
    if provider == "auto":
        # Prefer remote HF on hosts with a token (Railway demo)
        if config.HF_TOKEN:
            provider = "huggingface"
        else:
            provider = "local"

    if provider in ("hf", "huggingface", "remote"):
        return HuggingFaceEmbeddingFunction()

    # Local ST (heavy)
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    return SentenceTransformerEmbeddingFunction(model_name=config.EMBEDDING_MODEL)
