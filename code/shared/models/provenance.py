"""FR-5: machine-readable provenance block attached to every FR-1..FR-4
response. This is what lets SEC-2.3 audit logging reconstruct lineage
without re-deriving it after the fact.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from shared.ids import new_request_id, utcnow


class ProvenanceBlock(BaseModel):
    request_id: str = Field(default_factory=new_request_id)
    model_id: str
    model_version: str
    prompt_template_id: str
    prompt_template_version: str
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=utcnow)
    cache_hit: bool = False
