"""SEC-2.3 read side: the Internal Auditor persona's primary interaction —
reconstructing any historical AI-assisted decision from the audit log.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.db.models import AuditLogEntry


def list_audit_log(
    db: Session,
    endpoint: str | None = None,
    user_id: str | None = None,
    limit: int = 100,
) -> list[AuditLogEntry]:
    stmt = select(AuditLogEntry).order_by(AuditLogEntry.created_at.desc()).limit(min(limit, 500))
    if endpoint:
        stmt = stmt.where(AuditLogEntry.endpoint == endpoint)
    if user_id:
        stmt = stmt.where(AuditLogEntry.user_id == user_id)
    return list(db.execute(stmt).scalars().all())


def get_audit_entry(db: Session, request_id: str) -> AuditLogEntry | None:
    stmt = select(AuditLogEntry).where(AuditLogEntry.request_id == request_id)
    return db.execute(stmt).scalar_one_or_none()
