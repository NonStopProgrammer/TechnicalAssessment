"""EMBEDDING_PROVIDER config flag selects the implementation — see
.env.example and requirements/04-llm-orchestration-requirements.md's
LLM-2.3 "config-driven, not hardcoded" principle, applied here to
embeddings too.
"""

from abc import ABC, abstractmethod
from functools import lru_cache

from shared.config import get_settings

EMBEDDING_DIMENSION = 1024  # matches BAAI/bge-large-en-v1.5 (RAG-3.1)


class EmbeddingProvider(ABC):
    dimension: int = EMBEDDING_DIMENSION

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Returns one L2-normalized dense vector per input text."""

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "tei":
        from rag.embeddings.tei_embedder import TeiEmbedder

        return TeiEmbedder(settings.tei_embedding_url)

    from rag.embeddings.local_hash_embedder import LocalHashEmbedder

    return LocalHashEmbedder()
