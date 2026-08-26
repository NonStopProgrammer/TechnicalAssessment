"""RAG-3.1 production embedder: HuggingFace Text Embeddings Inference (TEI)
serving BAAI/bge-large-en-v1.5, self-hosted (see ADR-001, ADR-002 — no
regulated document text leaves the VPC for embedding either).

Activate with EMBEDDING_PROVIDER=tei once a TEI deployment is reachable at
TEI_EMBEDDING_URL. Retries with backoff per RAG-7.2; raises
EmbeddingServiceUnavailableError after exhausting retries so the ingestion
DAG task fails loudly (paged) rather than silently skipping embedding.
"""

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from rag.embeddings.base import EMBEDDING_DIMENSION, EmbeddingProvider
from rag.exceptions import EmbeddingServiceUnavailableError


class TeiEmbedder(EmbeddingProvider):
    def __init__(self, base_url: str, dimension: int = EMBEDDING_DIMENSION, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.dimension = dimension
        self.timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            return self._embed_with_retry(texts)
        except Exception as exc:  # noqa: BLE001 — RAG-7.2: exhausted retries -> typed error
            raise EmbeddingServiceUnavailableError(
                f"TEI embedding endpoint '{self.base_url}' unavailable after retries: {exc}"
            ) from exc

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}/embed", json={"inputs": texts})
            response.raise_for_status()
            return response.json()
