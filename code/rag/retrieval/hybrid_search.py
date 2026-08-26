"""RAG-4.1: dense + sparse retrieved in parallel per region, merged with
Reciprocal Rank Fusion. RAG-4.2: top 50 candidates. SEC-1.2: cross-
jurisdiction queries hit each region's collection independently and merge
*results*, never a single query spanning regions (that would require
centralizing regulated text in one place, which SEC-1.1 forbids).
"""

from qdrant_client.http.models import ScoredPoint

from rag.embeddings.base import get_embedding_provider
from rag.embeddings.sparse_vectorizer import vectorize_sparse
from rag.vectorstore.qdrant_store import build_jurisdiction_filter, get_qdrant_store
from shared.enums import Jurisdiction
from shared.models.chunk import Chunk, RetrievedChunk

ALL_JURISDICTIONS = [Jurisdiction.IN.value, Jurisdiction.EU.value, Jurisdiction.US.value]
RRF_K = 60


def _point_to_chunk(point: ScoredPoint) -> Chunk:
    payload = point.payload or {}
    return Chunk(
        chunk_id=payload["chunk_id"],
        doc_id=payload["doc_id"],
        clause_id=payload["clause_id"],
        section_path=payload["section_path"],
        text=payload["text"],
        framework=payload["framework"],
        jurisdiction=payload["jurisdiction"],
        doc_type=payload["doc_type"],
        effective_date=payload["effective_date"],
        version=payload["version"],
        superseded_by=payload.get("superseded_by"),
    )


def _rrf_fuse(
    dense_points: list[ScoredPoint], sparse_points: list[ScoredPoint], k: int = RRF_K
) -> dict[str, RetrievedChunk]:
    fusion_scores: dict[str, float] = {}
    dense_scores: dict[str, float] = {}
    sparse_scores: dict[str, float] = {}
    chunks: dict[str, Chunk] = {}

    for rank, point in enumerate(dense_points):
        pid = str(point.id)
        fusion_scores[pid] = fusion_scores.get(pid, 0.0) + 1.0 / (k + rank + 1)
        dense_scores[pid] = point.score
        chunks[pid] = _point_to_chunk(point)

    for rank, point in enumerate(sparse_points):
        pid = str(point.id)
        fusion_scores[pid] = fusion_scores.get(pid, 0.0) + 1.0 / (k + rank + 1)
        sparse_scores[pid] = point.score
        chunks.setdefault(pid, _point_to_chunk(point))

    return {
        pid: RetrievedChunk(
            chunk=chunks[pid],
            dense_score=dense_scores.get(pid, 0.0),
            sparse_score=sparse_scores.get(pid, 0.0),
            fusion_score=score,
        )
        for pid, score in fusion_scores.items()
    }


def hybrid_search(
    query_text: str,
    jurisdictions: list[str] | None = None,
    framework: str | None = None,
    candidate_limit: int = 50,
    as_of: str | None = None,
) -> list[RetrievedChunk]:
    store = get_qdrant_store()
    embedder = get_embedding_provider()
    dense_vector = embedder.embed_one(query_text)
    sparse = vectorize_sparse(query_text)

    target_jurisdictions = [j for j in (jurisdictions or ALL_JURISDICTIONS) if j != Jurisdiction.GLOBAL.value]
    merged: dict[str, RetrievedChunk] = {}

    for jurisdiction in target_jurisdictions:
        qfilter = build_jurisdiction_filter([jurisdiction], framework, as_of)
        dense_hits = store.search_dense(jurisdiction, dense_vector, qfilter, candidate_limit)
        sparse_hits = store.search_sparse(jurisdiction, sparse.indices, sparse.values, qfilter, candidate_limit)
        for pid, retrieved in _rrf_fuse(dense_hits, sparse_hits).items():
            if pid not in merged or retrieved.fusion_score > merged[pid].fusion_score:
                merged[pid] = retrieved

    ranked = sorted(merged.values(), key=lambda r: r.fusion_score, reverse=True)
    return ranked[:candidate_limit]
