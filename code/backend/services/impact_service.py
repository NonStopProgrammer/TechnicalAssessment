"""FR-3.4: read side of the human-in-the-loop review queue populated by
`agentic/impact/build_impact_graph.py` on ingestion. Never auto-applies a
policy change — a Compliance Head reviews and (outside this MVP's scope)
marks items resolved via direct DB/back-office action.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.db.models import ImpactReviewItem


def list_impact_review_items(db: Session, status: str | None = None) -> list[ImpactReviewItem]:
    stmt = select(ImpactReviewItem).order_by(ImpactReviewItem.created_at.desc())
    if status:
        stmt = stmt.where(ImpactReviewItem.status == status)
    return list(db.execute(stmt).scalars().all())
