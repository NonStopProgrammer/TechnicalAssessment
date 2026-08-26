"""RAG-4.3: re-ranking, 50 candidates down to top-k by query relevance."""

import re
from abc import ABC, abstractmethod
from functools import lru_cache

from shared.config import get_settings
from shared.models.chunk import RetrievedChunk

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:%|\.\d+)?")

# Stripped from the query before computing overlap. Without this, a
# natural-language question's function words ("what", "the", "under",
# "must") inflate the overlap denominator and suppress the score of a
# genuinely correct match almost as much as an irrelevant one — which
# defeats RAG-4.6's relevance floor as a way to tell them apart.
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being", "to", "of", "in",
        "on", "for", "and", "or", "but", "if", "what", "which", "who", "whom", "this", "that",
        "these", "those", "it", "as", "at", "by", "from", "with", "about", "under", "over",
        "into", "through", "during", "before", "after", "above", "below", "up", "down", "do",
        "does", "did", "can", "could", "should", "would", "will", "shall", "may", "might",
        "not", "no", "nor", "so", "than", "too", "very", "just", "any", "all", "both",
    }
)


class Reranker(ABC):
    @abstractmethod
    def rerank(self, query: str, candidates: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]: ...


class LexicalOverlapReranker(Reranker):
    """MVP default stand-in for the BAAI/bge-reranker-large cross-encoder.
    Blends the fusion score with query/chunk token overlap — a deliberately
    simple proxy that still rewards exact-term matches (defined terms,
    percentages, section numbers), which matters for regulatory text per
    RAG-4.1's rationale for pairing dense retrieval with a lexical signal.
    """

    def rerank(self, query: str, candidates: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        query_terms = set(_TOKEN_PATTERN.findall(query.lower())) - _STOPWORDS
        for candidate in candidates:
            chunk_terms = set(_TOKEN_PATTERN.findall(candidate.chunk.text.lower()))
            overlap = len(query_terms & chunk_terms) / len(query_terms) if query_terms and chunk_terms else 0.0
            candidate.rerank_score = round(0.5 * candidate.fusion_score + 0.5 * overlap, 6)
        ranked = sorted(candidates, key=lambda c: c.rerank_score or 0.0, reverse=True)
        return ranked[:top_k]


class CrossEncoderReranker(Reranker):
    """Production RAG-4.3 adapter: BAAI/bge-reranker-large via a TEI rerank
    endpoint. Activate with RERANKER_PROVIDER=cross_encoder.
    """

    def __init__(self, endpoint_url: str, timeout: float = 30.0):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.timeout = timeout

    def rerank(self, query: str, candidates: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        import httpx

        texts = [c.chunk.text for c in candidates]
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.endpoint_url}/rerank", json={"query": query, "texts": texts})
            response.raise_for_status()
            scores = response.json()  # [{"index": i, "score": s}, ...]

        score_by_index = {item["index"]: item["score"] for item in scores}
        for i, candidate in enumerate(candidates):
            candidate.rerank_score = score_by_index.get(i, 0.0)
        ranked = sorted(candidates, key=lambda c: c.rerank_score or 0.0, reverse=True)
        return ranked[:top_k]


@lru_cache
def get_reranker() -> Reranker:
    settings = get_settings()
    if settings.reranker_provider == "cross_encoder":
        return CrossEncoderReranker(settings.tei_rerank_url)
    return LexicalOverlapReranker()
