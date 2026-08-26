"""RAG-1.3 ingest-time metadata + RAG-5 versioning fields."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from shared.enums import DocType, Framework, Jurisdiction
from shared.ids import utcnow


class DocumentMetadata(BaseModel):
    doc_id: str
    title: str
    framework: Framework
    jurisdiction: Jurisdiction
    doc_type: DocType
    effective_date: date
    version: str
    supersedes_doc_id: str | None = None
    superseded_by: str | None = None  # RAG-5.1: set on the OLD record, never deleted
    checksum: str
    source_uri: str
    ingested_at: datetime = Field(default_factory=utcnow)

    def is_current(self, as_of: date | None = None) -> bool:
        """RAG-5.2 default retrieval filter: effective_date <= now AND not superseded."""
        reference = as_of or date.today()
        if self.effective_date > reference:
            return False
        if self.superseded_by is None:
            return True
        return False
