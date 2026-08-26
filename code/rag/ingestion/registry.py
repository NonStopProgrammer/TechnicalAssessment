"""RAG-5.4: Postgres/SQLite document_registry is the source of truth for the
version graph; RAG-1.4 idempotency and RAG-5.1 append-don't-overwrite are
both enforced here, in front of the vector store, not in Qdrant.
"""

from sqlalchemy.orm import Session

from rag.exceptions import DuplicateIngestionSkipped
from shared.db.models import DocumentRegistry
from shared.models.document import DocumentMetadata


def register_document(db: Session, metadata: DocumentMetadata) -> DocumentRegistry:
    existing = db.get(DocumentRegistry, metadata.doc_id)
    if existing is not None and existing.checksum == metadata.checksum:
        # RAG-1.4: identical bytes re-ingested -> no-op, not a new version.
        raise DuplicateIngestionSkipped(metadata.doc_id, metadata.checksum)

    row = DocumentRegistry(
        doc_id=metadata.doc_id,
        title=metadata.title,
        framework=metadata.framework.value,
        jurisdiction=metadata.jurisdiction.value,
        doc_type=metadata.doc_type.value,
        version=metadata.version,
        effective_date=metadata.effective_date,
        supersedes_doc_id=metadata.supersedes_doc_id,
        checksum=metadata.checksum,
        source_uri=metadata.source_uri,
        ingestion_status="ingested",
    )
    db.merge(row)

    if metadata.supersedes_doc_id:
        # RAG-5.1: mark the OLD record, never delete/overwrite it.
        superseded = db.get(DocumentRegistry, metadata.supersedes_doc_id)
        if superseded is not None:
            superseded.superseded_by = metadata.doc_id

    db.commit()
    return row


def quarantine_document(db: Session, doc_id: str, source_uri: str, reason: str) -> None:
    """RAG-7.1: malformed document is recorded, not silently dropped, and
    does not fail the whole ingestion DAG run.
    """
    row = DocumentRegistry(
        doc_id=doc_id,
        title=f"QUARANTINED: {source_uri}",
        framework="rbi",  # placeholder — unknown at quarantine time; not used for retrieval
        jurisdiction="GLOBAL",
        doc_type="circular",
        version="unknown",
        effective_date=__import__("datetime").date.today(),
        checksum="",
        source_uri=source_uri,
        ingestion_status="quarantined",
        quarantine_reason=reason,
    )
    db.merge(row)
    db.commit()


def get_current_version(db: Session, doc_id: str) -> DocumentRegistry | None:
    """RAG-5.2: default retrieval = latest effective version (superseded_by IS NULL)."""
    row = db.get(DocumentRegistry, doc_id)
    if row is None or row.superseded_by is not None:
        return None
    return row


def get_superseded_chain(db: Session, doc_id: str) -> list[DocumentRegistry]:
    """Walk backwards through `supersedes_doc_id` — used by FR-3.2 diffing."""
    chain = []
    current = db.get(DocumentRegistry, doc_id)
    while current is not None and current.supersedes_doc_id:
        prior = db.get(DocumentRegistry, current.supersedes_doc_id)
        if prior is None:
            break
        chain.append(prior)
        current = prior
    return chain
