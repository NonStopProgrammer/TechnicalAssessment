"""SEC-2.3 API schema — the Internal Auditor persona's read surface."""

from datetime import datetime

from pydantic import BaseModel


class AuditLogEntryResponse(BaseModel):
    id: int
    request_id: str
    user_id: str
    role: str
    endpoint: str
    input_redacted: dict
    retrieved_chunk_ids: list
    model_id: str | None
    model_version: str | None
    prompt_template_id: str | None
    prompt_template_version: str | None
    output_redacted: dict
    confidence_score: float | None
    human_override: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
