"""RAG-3.2: Qdrant client wrapper.

Runs in one of two modes, selected purely by config (no code change):
  - Embedded/local (QDRANT_URL unset): `QdrantClient(path=...)` — an
    on-disk, single-process Qdrant, zero external services. This is what
    lets the MVP run without Docker.
  - Server (QDRANT_URL set, e.g. by docker-compose or a real EKS
    deployment): talks to a real Qdrant instance over HTTP/gRPC.

RAG-7.3: query-time failures are wrapped as VectorStoreUnavailableError so
the retrieval pipeline can degrade gracefully (FR-1.5-style) instead of a
raw 500 reaching a compliance officer.
"""

import uuid
from functools import lru_cache

from qdrant_client import QdrantClient, models

from rag.exceptions import VectorStoreUnavailableError
from rag.vectorstore.schema import (
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    collection_name,
    payload_index_fields,
    sparse_vectors_config,
    vectors_config,
)
from shared.config import get_settings
from shared.enums import Jurisdiction
from shared.ids import utcnow
from shared.models.chunk import Chunk


def _point_id(chunk_id: str) -> str:
    """Qdrant point IDs must be an unsigned int or UUID — chunk_ids are
    human-readable strings (RAG-6.1-adjacent), so derive a stable UUID5.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class QdrantStore:
    def __init__(self):
        settings = get_settings()
        if settings.qdrant_url:
            self._client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
        else:
            self._client = QdrantClient(path=settings.qdrant_local_path)
        self._ensured: set[str] = set()

    def ensure_collection(self, jurisdiction: str) -> str:
        name = collection_name(jurisdiction)
        if name in self._ensured:
            return name
        try:
            exists = self._client.collection_exists(collection_name=name)
            if not exists:
                self._client.create_collection(
                    collection_name=name,
                    vectors_config=vectors_config(),
                    sparse_vectors_config=sparse_vectors_config(),
                )
                for field_name, schema in payload_index_fields():
                    self._client.create_payload_index(
                        collection_name=name, field_name=field_name, field_schema=schema
                    )
            self._ensured.add(name)
            return name
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreUnavailableError(f"could not ensure collection '{name}': {exc}") from exc

    def upsert_chunks(
        self,
        target_jurisdiction: str,
        chunks: list[Chunk],
        dense_vectors: list[list[float]],
        sparse_vectors: list[tuple[list[int], list[float]]],
    ) -> int:
        """`target_jurisdiction` selects the *collection* (i.e. the regional
        deployment a chunk is physically stored in) — it is deliberately
        independent of `chunk.jurisdiction` (the payload label). A GLOBAL
        regulation like Basel III is replicated into every region's
        collection (target_jurisdiction cycles through IN/EU/US) while each
        chunk keeps `jurisdiction=GLOBAL` in its payload, so citations still
        show the regulation's true scope — see
        rag/ingestion/pipeline.py::_embed_and_index.
        """
        if not chunks:
            return 0
        name = self.ensure_collection(target_jurisdiction)

        points = []
        for chunk, dense, (sparse_idx, sparse_val) in zip(chunks, dense_vectors, sparse_vectors, strict=True):
            points.append(
                models.PointStruct(
                    id=_point_id(chunk.chunk_id),
                    vector={
                        DENSE_VECTOR_NAME: dense,
                        SPARSE_VECTOR_NAME: models.SparseVector(indices=sparse_idx, values=sparse_val),
                    },
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "doc_id": chunk.doc_id,
                        "clause_id": chunk.clause_id,
                        "section_path": chunk.section_path,
                        "text": chunk.text,
                        "framework": chunk.framework.value,
                        "jurisdiction": chunk.jurisdiction.value,
                        "doc_type": chunk.doc_type.value,
                        "effective_date": chunk.effective_date.isoformat(),
                        "version": chunk.version,
                        "superseded_by": chunk.superseded_by,
                        "indexed_at": utcnow().isoformat(),
                    },
                )
            )

        try:
            self._client.upsert(collection_name=name, points=points, wait=True)
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreUnavailableError(f"upsert to '{name}' failed: {exc}") from exc
        return len(points)

    def search_dense(
        self, jurisdiction: str, vector: list[float], query_filter: models.Filter | None, limit: int
    ) -> list[models.ScoredPoint]:
        name = self.ensure_collection(jurisdiction)
        try:
            result = self._client.query_points(
                collection_name=name,
                query=vector,
                using=DENSE_VECTOR_NAME,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            return result.points
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreUnavailableError(f"dense search on '{name}' failed: {exc}") from exc

    def search_sparse(
        self,
        jurisdiction: str,
        indices: list[int],
        values: list[float],
        query_filter: models.Filter | None,
        limit: int,
    ) -> list[models.ScoredPoint]:
        name = self.ensure_collection(jurisdiction)
        try:
            result = self._client.query_points(
                collection_name=name,
                query=models.SparseVector(indices=indices, values=values),
                using=SPARSE_VECTOR_NAME,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            return result.points
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreUnavailableError(f"sparse search on '{name}' failed: {exc}") from exc

    def mark_superseded(self, jurisdiction: str, doc_id: str, superseded_by: str) -> None:
        """RAG-5.1 propagated to the vector store payload (registry in
        shared.db is still the source of truth — this keeps them in sync).
        """
        name = self.ensure_collection(jurisdiction)
        self._client.set_payload(
            collection_name=name,
            payload={"superseded_by": superseded_by},
            points=models.Filter(must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))]),
        )

    def snapshot(self, jurisdiction: str) -> str:
        """RAG-5.5: pre-ingestion snapshot allows reverting a bad ingest
        without reprocessing the whole corpus.
        """
        name = self.ensure_collection(jurisdiction)
        info = self._client.create_snapshot(collection_name=name)
        return info.name if info else ""


@lru_cache
def get_qdrant_store() -> QdrantStore:
    return QdrantStore()


def build_jurisdiction_filter(
    jurisdictions: list[str] | None,
    framework: str | None,
    as_of: str | None = None,
) -> models.Filter | None:
    """RAG-4.5: hard payload filters applied before fusion, plus RAG-5.2's
    default 'current version only' filter.

    A jurisdiction filter always admits GLOBAL-tagged content alongside the
    requested jurisdiction(s) — Basel III is tagged GLOBAL but applies in
    India via RBI adoption (see requirements/01-business-context-and-
    personas.md), so an IN-scoped query must not silently exclude it.

    `as_of` (ISO date string) implements FR-1.4/RAG-5.3's point-in-time
    query: instead of restricting to the current version
    (superseded_by IS NULL), it restricts to versions effective on or
    before that date. This is an approximation of the full version graph
    (it does not exclude a version superseded *before* `as_of`) that is
    sufficient for the MVP's single-amendment sample corpus; a production
    implementation would resolve the graph edge active at `as_of` exactly.
    """
    must: list[models.Condition] = []
    if as_of is None:
        must.append(models.IsNullCondition(is_null=models.PayloadField(key="superseded_by")))
    else:
        must.append(models.FieldCondition(key="effective_date", range=models.DatetimeRange(lte=as_of)))

    if jurisdictions:
        admitted = {*jurisdictions, Jurisdiction.GLOBAL.value}
        must.append(models.FieldCondition(key="jurisdiction", match=models.MatchAny(any=list(admitted))))
    if framework:
        must.append(models.FieldCondition(key="framework", match=models.MatchValue(value=framework)))
    return models.Filter(must=must) if must else None
