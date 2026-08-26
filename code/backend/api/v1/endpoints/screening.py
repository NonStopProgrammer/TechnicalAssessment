"""FR-2: transaction screening via the full compliance agent graph."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.deps import AuthenticatedUser, get_db, require_roles
from backend.services.screening_service import handle_screening_request
from shared.enums import UserRole
from shared.models.assessment import ComplianceAssessment
from shared.models.transaction import TransactionPayload

router = APIRouter(tags=["screening"])


@router.post("/screening", response_model=ComplianceAssessment)
def screen_transaction(
    payload: TransactionPayload,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles(UserRole.COMPLIANCE_OFFICER, UserRole.COMPLIANCE_HEAD)),
) -> ComplianceAssessment:
    return handle_screening_request(db, user, payload)
