"""MVP default embedder: deterministic hashed bag-of-words, no model
download, no GPU, no network call.

This is a stand-in for `rag/embeddings/tei_embedder.py` (BAAI/bge-large-en-
v1.5, RAG-3.1) — it is not a semantic embedding, but the hashing-trick
bag-of-words it produces still gives meaningful cosine similarity for
regulatory text specifically *because* that text leans on repeated defined
terms and section vocabulary (the same reason RAG-4.1 pairs dense retrieval
with a sparse/BM25 signal). Swap EMBEDDING_PROVIDER=tei for the real model
once GPU-backed TEI is available (see requirements-full.txt).
"""

import re
import zlib

import numpy as np

from rag.embeddings.base import EMBEDDING_DIMENSION, EmbeddingProvider

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:\.[a-z0-9]+)*")


def _stable_hash(token: str) -> int:
    """Python's builtin `hash()` is randomized per-process (PYTHONHASHSEED),
    which would silently desync embeddings computed at ingestion time from
    embeddings computed at query time in a different process. crc32 is
    stable across processes and runs.
    """
    return zlib.crc32(token.encode("utf-8"))


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


class LocalHashEmbedder(EmbeddingProvider):
    def __init__(self, dimension: int = EMBEDDING_DIMENSION, n_gram: int = 2):
        self.dimension = dimension
        self.n_gram = n_gram

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = np.zeros(self.dimension, dtype=np.float64)
        tokens = _tokenize(text)

        grams = list(tokens)
        for n in range(2, self.n_gram + 1):
            grams.extend(" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1))

        for gram in grams:
            h = _stable_hash(gram)
            idx = h % self.dimension
            sign = 1.0 if (h >> 1) % 2 == 0 else -1.0
            vector[idx] += sign

        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        return vector.tolist()
