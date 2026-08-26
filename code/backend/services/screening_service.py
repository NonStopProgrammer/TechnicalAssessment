"""FR-2: wires the compliance agent graph to the API layer, persists the
assessment for later reporting (FR-4), and writes the SEC-2.3 audit log.
"""

from sqlalchemy.orm import Session

from agentic.graph.build_graph import run_screening
from backend.core.audit import write_audit_log
from backend.core.security import AuthenticatedUser
from shared.db.models import AssessmentRecord
from shared.ids import new_request_id
from shared.models.assessment import ComplianceAssessment
from shared.models.transaction import TransactionPayload


def handle_screening_request(
    db: Session, user: AuthenticatedUser, payload: TransactionPayload
) -> ComplianceAssessment:
    request_id = new_request_id()
    assessment = run_screening(payload, request_id=request_id)

    audit_entry = write_audit_log(
        db,
        user,
        endpoint="screening",
        request_id=request_id,
        input_data=payload.model_dump(mode="json"),
        output_data=assessment.model_dump(mode="json"),
        provenance=assessment.provenance,
        confidence_score=assessment.confidence_score,
    )

    db.add(
        AssessmentRecord(
            transaction_id=assessment.transaction_id or request_id,
            jurisdiction=payload.jurisdictions[0] if payload.jurisdictions else "GLOBAL",
            transaction_type=payload.transaction_type.value,
            risk_rating=assessment.risk_rating.value,
            status=assessment.status.value,
            confidence_score=assessment.confidence_score,
            assessment_json=assessment.model_dump(mode="json"),
            request_id=audit_entry.request_id,  # FR-4.5: links a report line back to its audit trail entry
        )
    )
    db.commit()
    return assessment
