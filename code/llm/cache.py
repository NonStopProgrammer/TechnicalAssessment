"""LLM-2.5: cost control — a token budget enforced at the orchestration
layer, and a response cache in front of the generation tier for repeated
or near-duplicate queries.
"""

import time
from dataclasses import dataclass
from functools import lru_cache
from threading import Lock

import numpy as np

from rag.embeddings.base import get_embedding_provider

DEFAULT_TTL_SECONDS = 3600
SIMILARITY_THRESHOLD = 0.97
MAX_CACHE_ENTRIES = 500
MAX_TOTAL_TOKENS = 4096  # hard cap on context + generation tokens per request


class TokenBudgetExceeded(Exception):
    pass


def enforce_token_budget(context_tokens: int, requested_generation_tokens: int) -> int:
    """Returns the generation-token allowance actually granted, clipping it
    to stay under MAX_TOTAL_TOKENS rather than rejecting the request
    outright when only the *generation* side needs trimming.
    """
    remaining = MAX_TOTAL_TOKENS - context_tokens
    if remaining <= 0:
        raise TokenBudgetExceeded(
            f"context alone ({context_tokens} tokens) exceeds the {MAX_TOTAL_TOKENS}-token request budget"
        )
    return min(requested_generation_tokens, remaining)


@dataclass
class _CacheEntry:
    embedding: list[float]
    value: dict
    expires_at: float


class SemanticResponseCache:
    """MVP stand-in for GPTCache: reuses the same embedding provider as
    retrieval to find a near-duplicate prior query instead of running a
    second vector index solely for caching. Demonstrates the LLM-2.5
    cost-control pattern; GPTCache's dedicated similarity/eviction backend
    is the production upgrade (same interface, see `get_response_cache`).
    """

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS, similarity_threshold: float = SIMILARITY_THRESHOLD):
        self._entries: list[_CacheEntry] = []
        self._ttl_seconds = ttl_seconds
        self._similarity_threshold = similarity_threshold
        self._lock = Lock()

    def get(self, query: str) -> dict | None:
        embedder = get_embedding_provider()
        query_vector = np.array(embedder.embed_one(query))
        now = time.time()

        with self._lock:
            self._entries = [e for e in self._entries if e.expires_at > now]
            best_score, best_value = 0.0, None
            for entry in self._entries:
                score = float(np.dot(query_vector, np.array(entry.embedding)))
                if score > best_score:
                    best_score, best_value = score, entry.value

        return best_value if best_score >= self._similarity_threshold else None

    def set(self, query: str, value: dict) -> None:
        embedder = get_embedding_provider()
        query_vector = embedder.embed_one(query)
        with self._lock:
            self._entries.append(
                _CacheEntry(embedding=query_vector, value=value, expires_at=time.time() + self._ttl_seconds)
            )
            if len(self._entries) > MAX_CACHE_ENTRIES:
                self._entries.pop(0)


@lru_cache
def get_response_cache() -> SemanticResponseCache:
    return SemanticResponseCache()
