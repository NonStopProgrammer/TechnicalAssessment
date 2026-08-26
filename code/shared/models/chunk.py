"""RAG-2.4 chunk-level metadata inheritance + RAG-4 retrieval scoring."""

from datetime import date

from pydantic import BaseModel

from shared.enums import DocType, Framework, Jurisdiction
from shared.ids import citation_key


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    clause_id: str
    section_path: str
    text: str
    framework: Framework
    jurisdiction: Jurisdiction
    doc_type: DocType
    effective_date: date
    version: str
    superseded_by: str | None = None

    @property
    def citation_key(self) -> str:
        return citation_key(self.doc_id, self.clause_id, self.version)


class RetrievedChunk(BaseModel):
    chunk: Chunk
    dense_score: float = 0.0
    sparse_score: float = 0.0
    fusion_score: float = 0.0
    rerank_score: float | None = None

    @property
    def final_score(self) -> float:
        return self.rerank_score if self.rerank_score is not None else self.fusion_score
