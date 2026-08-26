"""FR-1: wires the agentic.qa fast path to the API layer + SEC-2.3 audit log."""

from sqlalchemy.orm import Session

from agentic.qa import answer_question
from backend.core.audit import write_audit_log
from backend.core.security import AuthenticatedUser
from backend.schemas.qa import QaRequest, QaResponse
from shared.ids import new_request_id


def handle_qa_request(db: Session, user: AuthenticatedUser, payload: QaRequest) -> QaResponse:
    request_id = new_request_id()
    answer = answer_question(
        query=payload.query, jurisdictions=payload.jurisdictions, framework=payload.framework, as_of=payload.as_of
    )

    response = QaResponse(
        answer=answer.answer,
        status=answer.status,
        citations=[c.display for c in answer.citations],
        provenance=answer.provenance.model_dump(mode="json") if answer.provenance else None,
    )

    write_audit_log(
        db,
        user,
        endpoint="qa",
        request_id=request_id,
        input_data=payload.model_dump(mode="json"),
        output_data=response.model_dump(mode="json"),
        provenance=answer.provenance,
    )
    return response
