"""FR-3.4: read-only human-in-the-loop review queue."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.deps import AuthenticatedUser, get_db, require_roles
from backend.schemas.impact import ImpactReviewItemResponse
from backend.services.impact_service import list_impact_review_items
from shared.enums import UserRole

router = APIRouter(tags=["impact"])


@router.get("/impact-review-queue", response_model=list[ImpactReviewItemResponse])
def get_impact_review_queue(
    status: str | None = None,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles(UserRole.COMPLIANCE_HEAD)),
) -> list[ImpactReviewItemResponse]:
    items = list_impact_review_items(db, status=status)
    return [ImpactReviewItemResponse.model_validate(item) for item in items]
