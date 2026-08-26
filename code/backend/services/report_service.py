"""FR-4: structured compliance report generation.

FR-4.3: counts/statistics are computed deterministically from persisted
`AssessmentRecord` rows (see screening_service.py); only the narrative
prose is LLM-generated, and is checked against the computed numbers by
the numeric-consistency guardrail (LLM-4.6) before being shipped — a
mismatch falls back to a deterministic templated sentence rather than
shipping a report with a hallucinated statistic.
"""

from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.audit import write_audit_log
from backend.core.security import AuthenticatedUser
from backend.schemas.reports import ReportFilter, ReportResponse
from llm.guardrails.numeric_consistency import check_numeric_consistency
from llm.prompts.registry import render_prompt
from llm.response_models import NarrativeOutput
from llm.structured_output import GenerationDegraded, generate_structured
from shared.config import get_settings
from shared.db.models import AssessmentRecord, ReportRecord
from shared.enums import RiskRating
from shared.ids import new_request_id
from shared.logging import get_logger

logger = get_logger(__name__)


def generate_report(db: Session, user: AuthenticatedUser, filters: ReportFilter) -> ReportResponse:
    request_id = new_request_id()
    records = _query_records(db, filters)
    stats = _compute_stats(records)  # FR-4.3: deterministic
    narrative, key_points = _draft_narrative(stats, filters)  # FR-4.3: generative, prose only

    consistency = check_numeric_consistency(narrative, stats)
    if not consistency.is_consistent:  # LLM-4.6: block, don't ship, a hallucinated statistic
        logger.warning("report.numeric_consistency_failed", unexplained=consistency.unexplained_numbers)
        narrative = _fallback_narrative(stats)
        key_points = []

    markdown = _render_markdown(filters, stats, narrative, key_points, records)
    report_id = f"rpt_{new_request_id()[4:]}"
    markdown_path = _save_markdown(report_id, markdown)

    # Audit log first — ReportRecord.request_id is a foreign key into it
    # (FR-4.5: every report traces back to the audit trail entry it came from).
    write_audit_log(
        db,
        user,
        endpoint="reports",
        request_id=request_id,
        input_data=filters.model_dump(mode="json"),
        output_data={"report_id": report_id, "summary_stats": stats},
    )

    db.add(
        ReportRecord(
            report_id=report_id,
            filters=filters.model_dump(mode="json"),
            transaction_ids=[r.transaction_id for r in records],
            summary_stats=stats,
            narrative=narrative,
            markdown_path=str(markdown_path),
            request_id=request_id,
        )
    )
    db.commit()

    return ReportResponse(
        report_id=report_id,
        filters=filters.model_dump(mode="json"),
        summary_stats=stats,
        narrative=narrative,
        markdown=markdown,
        transaction_count=len(records),
    )


def get_report_markdown(db: Session, report_id: str) -> str | None:
    record = db.get(ReportRecord, report_id)
    if record is None or not record.markdown_path:
        return None
    path = Path(record.markdown_path)
    return path.read_text(encoding="utf-8") if path.exists() else None


def render_report_pdf(markdown_text: str) -> bytes:
    """FR-4.4: PDF export. A plain paragraph dump of the markdown text via
    fpdf2's core (non-Unicode) fonts, not full markdown rendering — enough
    to satisfy "exportable to PDF" for an MVP; a production implementation
    would render through a proper markdown-to-PDF pipeline.
    """
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    safe_text = markdown_text.encode("latin-1", "replace").decode("latin-1")
    for line in safe_text.split("\n"):
        # multi_cell leaves the X cursor wherever it stopped; without
        # resetting it to the left margin before every call, X drifts
        # right on each successive line until the remaining width hits
        # zero and fpdf raises "Not enough horizontal space".
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 6, line or " ")
    return bytes(pdf.output())


def _query_records(db: Session, filters: ReportFilter) -> list[AssessmentRecord]:
    stmt = select(AssessmentRecord)
    if filters.date_from:
        stmt = stmt.where(AssessmentRecord.created_at >= datetime.combine(filters.date_from, datetime.min.time()))
    if filters.date_to:
        stmt = stmt.where(AssessmentRecord.created_at <= datetime.combine(filters.date_to, datetime.max.time()))
    if filters.transaction_type:
        stmt = stmt.where(AssessmentRecord.transaction_type == filters.transaction_type)
    if filters.jurisdiction:
        stmt = stmt.where(AssessmentRecord.jurisdiction == filters.jurisdiction)

    records = list(db.execute(stmt).scalars().all())
    if filters.min_risk_rating:
        floor = RiskRating(filters.min_risk_rating).severity
        records = [r for r in records if RiskRating(r.risk_rating).severity >= floor]
    return records


def _compute_stats(records: list[AssessmentRecord]) -> dict:
    by_risk_rating: dict[str, int] = {}
    by_framework: dict[str, int] = {}
    for record in records:
        by_risk_rating[record.risk_rating] = by_risk_rating.get(record.risk_rating, 0) + 1
        for framework in record.assessment_json.get("applicable_frameworks", []):
            by_framework[framework] = by_framework.get(framework, 0) + 1

    high_or_above = sum(1 for r in records if RiskRating(r.risk_rating).severity >= RiskRating.HIGH.severity)
    return {
        "total_transactions": len(records),
        "high_or_above_count": high_or_above,
        "by_framework": by_framework,
        "by_risk_rating": by_risk_rating,
    }


def _draft_narrative(stats: dict, filters: ReportFilter) -> tuple[str, list[str]]:
    period = f"{filters.date_from or 'inception'} to {filters.date_to or 'present'}"
    prompt = render_prompt("report_narrative", period=period, stats=stats)
    try:
        generation = generate_structured(
            task="report_narrative",
            template_id=prompt.template_id,
            template_version=prompt.version,
            system_prompt=prompt.system_prompt,
            user_prompt=prompt.user_prompt,
            response_model=NarrativeOutput,
        )
        return generation.parsed.narrative, generation.parsed.key_points
    except GenerationDegraded as exc:
        logger.warning("report.narrative_degraded", error=str(exc))
        return _fallback_narrative(stats), []


def _fallback_narrative(stats: dict) -> str:
    return (
        f"{stats['total_transactions']} transaction(s) were assessed in this period, of which "
        f"{stats['high_or_above_count']} were rated HIGH or CRITICAL."
    )


def _render_markdown(
    filters: ReportFilter, stats: dict, narrative: str, key_points: list[str], records: list[AssessmentRecord]
) -> str:
    lines = [
        "# FinServ Compliance Report",
        "",
        f"Filters: {filters.model_dump(mode='json', exclude_none=True)}",
        "",
        "## Executive Summary",
        narrative,
    ]
    if key_points:
        lines += [""] + [f"- {point}" for point in key_points]

    lines += [
        "",
        "## Methodology",
        "Per-transaction risk assessments are produced by the automated compliance agent "
        "(deterministic rule scoring against cited regulatory context, LLM-drafted narrative "
        "only). This report aggregates already-computed assessments rather than re-running "
        "assessment logic (see AGENT-4).",
        "",
        "## Aggregate Risk Trend",
        f"- Total transactions: {stats['total_transactions']}",
        f"- Rated HIGH or CRITICAL: {stats['high_or_above_count']}",
        f"- By risk rating: {stats['by_risk_rating']}",
        f"- By framework: {stats['by_framework']}",
        "",
        "## Per-Transaction Assessments",
    ]
    for record in records:
        lines.append(
            f"- `{record.transaction_id}` — {record.risk_rating} ({record.transaction_type}, "
            f"{record.jurisdiction}) — audit trail request `{record.request_id}`"
        )

    lines += ["", "## Citations Appendix"]
    seen: set[str] = set()
    for record in records:
        for citation in record.assessment_json.get("citations", []):
            key = citation.get("citation_key")
            if key and key not in seen:
                seen.add(key)
                lines.append(f"- [{citation['doc_id']} §{citation['clause_id']}, v:{citation['version']}]")

    return "\n".join(lines)


def _save_markdown(report_id: str, markdown: str) -> Path:
    settings = get_settings()
    reports_dir = settings.code_root / "var" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{report_id}.md"
    path.write_text(markdown, encoding="utf-8")
    return path
