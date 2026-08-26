"""FR-1 API schemas."""

from pydantic import BaseModel, Field


class QaRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)  # FR-1.1
    jurisdictions: list[str] | None = None
    framework: str | None = None
    as_of: str | None = None  # FR-1.4 point-in-time query, ISO date


class QaResponse(BaseModel):
    answer: str
    status: str
    citations: list[str]
    provenance: dict | None = None
