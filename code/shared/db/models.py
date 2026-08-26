"""ORM tables. SQLAlchemy 2.0 typed-mapping style."""

from datetime import date, datetime

from sqlalchemy import JSON, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base
from shared.ids import utcnow


class DocumentRegistry(Base):
    """RAG-5.4: source of truth for the version graph. Qdrant payloads are a
    denormalized, rebuildable projection of these rows.
    """

    __tablename__ = "document_registry"

    doc_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    framework: Mapped[str] = mapped_column(String(30), index=True)
    jurisdiction: Mapped[str] = mapped_column(String(10), index=True)
    doc_type: Mapped[str] = mapped_column(String(30))
    version: Mapped[str] = mapped_column(String(30))
    effective_date: Mapped[date]
    supersedes_doc_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    superseded_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    source_uri: Mapped[str] = mapped_column(String(500))
    ingestion_status: Mapped[str] = mapped_column(String(20), default="ingested")  # RAG-7.1 quarantine
    quarantine_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(default=utcnow)


class AuditLogEntry(Base):
    """SEC-2.3: one row per FR-1..FR-4 request. Mirrored to S3 Object Lock
    (WORM) in production for SEC-2.4 tamper-evidence — the mirror step is a
    background job outside this MVP's scope, called out in backend/README.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(120), index=True)
    role: Mapped[str] = mapped_column(String(40))
    endpoint: Mapped[str] = mapped_column(String(120), index=True)
    input_redacted: Mapped[dict] = mapped_column(JSON)
    retrieved_chunk_ids: Mapped[list] = mapped_column(JSON, default=list)
    model_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    prompt_template_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_template_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    output_redacted: Mapped[dict] = mapped_column(JSON)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    human_override: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    __table_args__ = (Index("ix_audit_log_endpoint_created", "endpoint", "created_at"),)


class SeededTransaction(Base):
    """AGENT-1.3: mocked transaction store standing in for a core-banking
    integration (see requirements/11-non-goals-and-assumptions.md).
    """

    __tablename__ = "seeded_transactions"

    transaction_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class ReportRecord(Base):
    """FR-4: generated compliance reports, linked back to the assessments
    (and therefore audit log rows, FR-4.5) they were built from.
    """

    __tablename__ = "report_records"

    report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filters: Mapped[dict] = mapped_column(JSON)
    transaction_ids: Mapped[list] = mapped_column(JSON, default=list)
    summary_stats: Mapped[dict] = mapped_column(JSON)
    narrative: Mapped[str] = mapped_column(Text)
    markdown_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    request_id: Mapped[str] = mapped_column(String(64), ForeignKey("audit_log.request_id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class AssessmentRecord(Base):
    """Persisted FR-2 output. FR-4's report generation "orchestrates N
    already-computed FR-2 assessments plus deterministic aggregation" —
    this table is what makes an assessment computed once available to
    report on later without re-running the agent graph (AGENT-4).
    """

    __tablename__ = "assessment_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String(64), index=True)
    jurisdiction: Mapped[str] = mapped_column(String(10), index=True)
    transaction_type: Mapped[str] = mapped_column(String(40), index=True)
    risk_rating: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20))
    confidence_score: Mapped[float] = mapped_column(Float)
    assessment_json: Mapped[dict] = mapped_column(JSON)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)


class ImpactReviewItem(Base):
    """FR-3.4: human-in-the-loop review queue populated by the ingestion
    impact-scan trigger (FR-3.1), never auto-applied.
    """

    __tablename__ = "impact_review_queue"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    new_doc_id: Mapped[str] = mapped_column(String(80), index=True)
    superseded_doc_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    changed_clauses: Mapped[list] = mapped_column(JSON, default=list)
    affected_transaction_types: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="pending_review")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
