"""FR-4: structured compliance report generation."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from backend.api.deps import AuthenticatedUser, get_db, require_roles
from backend.schemas.reports import ReportFilter, ReportResponse
from backend.services.report_service import generate_report, get_report_markdown, render_report_pdf
from shared.enums import UserRole

router = APIRouter(tags=["reports"])


@router.post("/reports", response_model=ReportResponse)
def create_report(
    filters: ReportFilter,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles(UserRole.COMPLIANCE_HEAD)),
) -> ReportResponse:
    return generate_report(db, user, filters)


@router.get("/reports/{report_id}/markdown", response_class=PlainTextResponse)
def download_report_markdown(
    report_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles(UserRole.COMPLIANCE_HEAD, UserRole.INTERNAL_AUDITOR)),
) -> str:
    markdown = get_report_markdown(db, report_id)
    if markdown is None:
        raise HTTPException(status_code=404, detail="report not found")
    return markdown


@router.get("/reports/{report_id}/pdf")
def download_report_pdf(
    report_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles(UserRole.COMPLIANCE_HEAD, UserRole.INTERNAL_AUDITOR)),
) -> Response:
    markdown = get_report_markdown(db, report_id)
    if markdown is None:
        raise HTTPException(status_code=404, detail="report not found")
    return Response(content=render_report_pdf(markdown), media_type="application/pdf")
