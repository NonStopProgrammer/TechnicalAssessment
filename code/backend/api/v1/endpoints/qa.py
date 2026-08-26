"""FR-1: natural-language regulatory Q&A."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.deps import AuthenticatedUser, get_db, require_roles
from backend.schemas.qa import QaRequest, QaResponse
from backend.services.qa_service import handle_qa_request
from shared.enums import UserRole

router = APIRouter(tags=["qa"])


@router.post("/qa", response_model=QaResponse)
def ask_question(
    payload: QaRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles(UserRole.COMPLIANCE_OFFICER, UserRole.COMPLIANCE_HEAD)),
) -> QaResponse:
    return handle_qa_request(db, user, payload)
