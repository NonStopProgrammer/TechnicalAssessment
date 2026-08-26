"""RAG-4 end-to-end retrieval: hybrid search -> re-rank -> relevance floor
-> contextual compression. This is the single entry point used by both
FR-1's fast path (backend/app/services/qa_service.py) and the
`search_regulations` agent tool (agentic/tools/search_regulations.py) —
one implementation, two callers, per AGENT-4's design intent.
"""

from dataclasses import dataclass, field

from rag.retrieval.compression import get_compressor
from rag.retrieval.hybrid_search import hybrid_search
from rag.retrieval.reranker import get_reranker
from shared.config import get_settings
from shared.models.chunk import RetrievedChunk


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk] = field(default_factory=list)
    below_relevance_floor: bool = False
    empty_result: bool = False

    @property
    def has_usable_context(self) -> bool:
        return bool(self.chunks) and not self.below_relevance_floor and not self.empty_result


def retrieve(
    query_text: str,
    jurisdictions: list[str] | None = None,
    framework: str | None = None,
    top_k: int = 8,
    candidate_limit: int = 50,
    as_of: str | None = None,
) -> RetrievalResult:
    settings = get_settings()
    candidates = hybrid_search(query_text, jurisdictions, framework, candidate_limit, as_of)

    if not candidates:
        return RetrievalResult(empty_result=True)  # RAG-7.4: distinct from a relevance-floor miss

    reranker = get_reranker()
    top_chunks = reranker.rerank(query_text, candidates, top_k)

    if not top_chunks or top_chunks[0].final_score < settings.citation_relevance_floor:
        return RetrievalResult(chunks=top_chunks, below_relevance_floor=True)  # RAG-4.6 -> FR-1.5

    compressor = get_compressor()
    compressed = compressor.compress(query_text, top_chunks)
    return RetrievalResult(chunks=compressed)
