"""FR-1.3 / RAG-6 citation rendering, shared by QA, screening, and reports."""

from pydantic import BaseModel

from shared.enums import Framework
from shared.ids import format_citation_display


class Citation(BaseModel):
    citation_key: str
    doc_id: str
    clause_id: str
    version: str
    framework: Framework
    title: str
    snippet: str

    @property
    def display(self) -> str:
        return format_citation_display(self.doc_id, self.clause_id, self.version)
