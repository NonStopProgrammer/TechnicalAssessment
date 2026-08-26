"""FR-3 API schemas."""

from datetime import datetime

from pydantic import BaseModel


class ImpactReviewItemResponse(BaseModel):
    id: int
    new_doc_id: str
    superseded_doc_id: str | None
    changed_clauses: list[dict]
    affected_transaction_types: list[str]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
