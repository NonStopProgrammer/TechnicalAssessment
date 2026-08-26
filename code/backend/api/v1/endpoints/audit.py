"""SEC-2.3 read side: the Internal Auditor persona's primary interaction —
read-only, no query/screen access needed (SEC-2.2).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import AuthenticatedUser, get_db, require_roles
from backend.schemas.audit import AuditLogEntryResponse
from backend.services.audit_service import get_audit_entry, list_audit_log
from shared.enums import UserRole

router = APIRouter(tags=["audit"])


@router.get("/audit-log", response_model=list[AuditLogEntryResponse])
def get_audit_log(
    endpoint: str | None = None,
    user_id: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_roles(UserRole.INTERNAL_AUDITOR)),
) -> list[AuditLogEntryResponse]:
    entries = list_audit_log(db, endpoint=endpoint, user_id=user_id, limit=limit)
    return [AuditLogEntryResponse.model_validate(entry) for entry in entries]


@router.get("/audit-log/{request_id}", response_model=AuditLogEntryResponse)
def get_audit_log_entry(
    request_id: str,
    db: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_roles(UserRole.INTERNAL_AUDITOR)),
) -> AuditLogEntryResponse:
    entry = get_audit_entry(db, request_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="audit log entry not found")
    return AuditLogEntryResponse.model_validate(entry)
