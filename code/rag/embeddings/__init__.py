"""RAG-3.1: embedding provider abstraction — swap local_hash <-> tei via config."""

from rag.embeddings.base import EmbeddingProvider, get_embedding_provider

__all__ = ["EmbeddingProvider", "get_embedding_provider"]
