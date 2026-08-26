"""AGENT-1.2: wraps the RAG pipeline; returns re-ranked, cited chunks."""

from rag.retrieval.pipeline import RetrievalResult, retrieve


def search_regulations(
    query: str,
    jurisdictions: list[str] | None = None,
    framework: str | None = None,
    top_k: int = 8,
) -> RetrievalResult:
    return retrieve(query_text=query, jurisdictions=jurisdictions, framework=framework, top_k=top_k)
