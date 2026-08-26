"""RAG-1.5: ingestion orchestrator — fetch -> parse -> clean -> chunk ->
embed -> upsert -> impact-scan trigger (FR-3.1).

This module is the callable core that `rag/dags/ingestion_dag.py` (Apache
Airflow, production) wraps as a sequence of tasks. It is also called
directly by `scripts/seed_corpus.py` for local/CI use — the DAG adds
scheduling, retries-as-infra, and auditable run history (RAG-1.5, SEC-2 tie-
in) on top of the same functions, it does not duplicate their logic.
"""

from dataclasses import dataclass
from pathlib import Path

from rag.chunking.clause_chunker import chunk_document
from rag.embeddings.base import get_embedding_provider
from rag.embeddings.sparse_vectorizer import vectorize_sparse
from rag.exceptions import DuplicateIngestionSkipped, UnparseableDocumentError
from rag.ingestion.metadata_extraction import extract_metadata
from rag.ingestion.parsers import parse_document
from rag.ingestion.registry import quarantine_document, register_document
from rag.vectorstore.qdrant_store import get_qdrant_store
from shared.db.base import session_scope
from shared.enums import Jurisdiction
from shared.logging import get_logger
from shared.models.chunk import Chunk
from shared.models.document import DocumentMetadata

logger = get_logger(__name__)

REGIONAL_JURISDICTIONS = [Jurisdiction.IN.value, Jurisdiction.EU.value, Jurisdiction.US.value]


@dataclass
class IngestionOutcome:
    doc_id: str
    status: str  # "ingested" | "skipped_duplicate" | "quarantined"
    chunks_indexed: int = 0
    reason: str | None = None


def ingest_file(path: str | Path) -> IngestionOutcome:
    path = Path(path)

    try:
        parsed = parse_document(path)
        metadata = extract_metadata(parsed)
    except UnparseableDocumentError as exc:
        # RAG-7.1: quarantined with a logged reason, does not fail the whole run.
        with session_scope() as db:
            quarantine_document(db, doc_id=path.stem, source_uri=str(path), reason=exc.reason)
        logger.warning("ingestion.quarantined", source=str(path), reason=exc.reason)
        return IngestionOutcome(doc_id=path.stem, status="quarantined", reason=exc.reason)

    with session_scope() as db:
        try:
            register_document(db, metadata)
        except DuplicateIngestionSkipped:
            logger.info("ingestion.duplicate_skipped", doc_id=metadata.doc_id)
            return IngestionOutcome(doc_id=metadata.doc_id, status="skipped_duplicate")

    chunks = chunk_document(parsed.raw_text, metadata)
    _embed_and_index(chunks, metadata.jurisdiction.value)

    if metadata.supersedes_doc_id:
        store = get_qdrant_store()
        for jurisdiction in _target_jurisdictions(metadata.jurisdiction.value):
            store.mark_superseded(jurisdiction, metadata.supersedes_doc_id, metadata.doc_id)
        _trigger_impact_scan(metadata)  # FR-3.1: triggered by ingestion, never manual

    logger.info("ingestion.completed", doc_id=metadata.doc_id, chunks=len(chunks))
    return IngestionOutcome(doc_id=metadata.doc_id, status="ingested", chunks_indexed=len(chunks))


def ingest_directory(directory: str | Path) -> list[IngestionOutcome]:
    directory = Path(directory)
    supported = {".md", ".txt", ".html", ".htm", ".pdf", ".docx"}
    outcomes = []
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix.lower() in supported:
            outcomes.append(ingest_file(path))
    return outcomes


def _target_jurisdictions(doc_jurisdiction: str) -> list[str]:
    """SEC-1.2: a GLOBAL-applicability regulation (e.g. Basel III) is
    replicated into every region's collection at ingest time so each region
    can answer queries about it without a cross-region call at query time.
    """
    if doc_jurisdiction == Jurisdiction.GLOBAL.value:
        return REGIONAL_JURISDICTIONS
    return [doc_jurisdiction]


def _embed_and_index(chunks: list[Chunk], doc_jurisdiction: str) -> None:
    if not chunks:
        return
    embedder = get_embedding_provider()
    dense_vectors = embedder.embed([c.text for c in chunks])
    sparse_vectors = [(sv.indices, sv.values) for sv in (vectorize_sparse(c.text) for c in chunks)]

    store = get_qdrant_store()
    for jurisdiction in _target_jurisdictions(doc_jurisdiction):
        # Chunks keep their original `jurisdiction` payload (e.g. GLOBAL)
        # even when physically replicated into a regional collection —
        # citations must still reflect the regulation's true scope.
        store.upsert_chunks(jurisdiction, chunks, dense_vectors, sparse_vectors)


def _trigger_impact_scan(metadata: DocumentMetadata) -> None:
    from agentic.impact.build_impact_graph import run_impact_scan

    run_impact_scan(new_doc_id=metadata.doc_id, superseded_doc_id=metadata.supersedes_doc_id)
