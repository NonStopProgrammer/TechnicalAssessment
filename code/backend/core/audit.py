"""SEC-2.3: one audit-log row per FR-1..FR-4 request — user+role, endpoint,
PII-redacted input/output, retrieved chunk ids, model+prompt version, and
confidence score. This table is the Internal Auditor persona's primary
deliverable (see requirements/01-business-context-and-personas.md).
"""

from sqlalchemy.orm import Session

from backend.core.security import AuthenticatedUser
from llm.guardrails.pii_redaction import get_pii_redactor
from shared.db.models import AuditLogEntry
from shared.models.provenance import ProvenanceBlock


def write_audit_log(
    db: Session,
    user: AuthenticatedUser,
    endpoint: str,
    request_id: str,
    input_data: dict,
    output_data: dict,
    provenance: ProvenanceBlock | None = None,
    confidence_score: float | None = None,
) -> AuditLogEntry:
    redactor = get_pii_redactor()  # LLM-4.3 / SEC-3.3: redact before it ever reaches a log row
    entry = AuditLogEntry(
        request_id=request_id,
        user_id=user.user_id,
        role=user.role.value,
        endpoint=endpoint,
        input_redacted=redactor.redact_dict(input_data),
        retrieved_chunk_ids=provenance.retrieved_chunk_ids if provenance else [],
        model_id=provenance.model_id if provenance else None,
        model_version=provenance.model_version if provenance else None,
        prompt_template_id=provenance.prompt_template_id if provenance else None,
        prompt_template_version=provenance.prompt_template_version if provenance else None,
        output_redacted=redactor.redact_dict(output_data),
        confidence_score=confidence_score,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
