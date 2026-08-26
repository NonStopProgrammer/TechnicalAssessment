"""FR-4 API schemas."""

from datetime import date

from pydantic import BaseModel


class ReportFilter(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    transaction_type: str | None = None
    jurisdiction: str | None = None
    min_risk_rating: str | None = None  # FR-4.1


class ReportResponse(BaseModel):
    report_id: str
    filters: dict
    summary_stats: dict
    narrative: str
    markdown: str
    transaction_count: int
