from datetime import date

from agentic.tools.calculate_risk_rating import calculate_risk_rating
from agentic.tools.cross_reference_frameworks import cross_reference_frameworks
from agentic.tools.generate_citation_bundle import generate_citation_bundle
from shared.enums import CustomerType, DocType, Framework, Jurisdiction, KycStatus, RiskRating, TransactionType
from shared.models.chunk import Chunk, RetrievedChunk
from shared.models.transaction import TransactionPayload


def _transaction(**overrides) -> TransactionPayload:
    defaults = dict(
        amount=1000,
        currency="USD",
        counterparty="Test Counterparty",
        counterparty_kyc_status=KycStatus.VERIFIED,
        jurisdictions=["US"],
        instrument_type="wire_transfer",
        customer_type=CustomerType.INSTITUTIONAL,
        transaction_type=TransactionType.CROSS_BORDER_PAYMENT,
    )
    defaults.update(overrides)
    return TransactionPayload(**defaults)


def _chunk(framework: Framework, clause_id: str, text: str) -> RetrievedChunk:
    chunk = Chunk(
        chunk_id=f"{framework.value}::{clause_id}",
        doc_id=f"doc-{framework.value}",
        clause_id=clause_id,
        section_path=clause_id,
        text=text,
        framework=framework,
        jurisdiction=Jurisdiction.GLOBAL,
        doc_type=DocType.REGULATION,
        effective_date=date(2023, 1, 1),
        version="2023-01-01",
    )
    return RetrievedChunk(chunk=chunk, fusion_score=0.9, rerank_score=0.9)


# --- calculate_risk_rating: the assignment's 4 reference scenarios + 1 ambiguous case ---


def test_scenario_1_cross_border_payment_to_non_kyc_verified_high_risk_is_critical_or_high():
    t = _transaction(
        amount=2_000_000,
        counterparty_kyc_status=KycStatus.NOT_VERIFIED,
        counterparty_jurisdiction_risk="high",
        transaction_type=TransactionType.CROSS_BORDER_PAYMENT,
    )
    result = calculate_risk_rating(t)

    assert result.risk_rating in (RiskRating.CRITICAL, RiskRating.HIGH)
    assert any(f.framework == "rbi" for f in result.findings)


def test_scenario_2_intra_group_derivative_exceeding_large_exposure_cites_basel():
    t = _transaction(
        amount=75_000_000,
        customer_type=CustomerType.INTRA_GROUP,
        transaction_type=TransactionType.DERIVATIVE_TRADE,
        counterparty_kyc_status=KycStatus.VERIFIED,
    )
    result = calculate_risk_rating(t)

    assert any(f.framework == "basel_iii" for f in result.findings)
    assert result.risk_rating.severity >= RiskRating.MEDIUM.severity


def test_scenario_3_retail_investment_without_appropriateness_assessment_cites_mifid():
    t = _transaction(
        amount=150_000,
        customer_type=CustomerType.RETAIL,
        transaction_type=TransactionType.INVESTMENT,
        is_appropriateness_assessed=False,
        counterparty_kyc_status=KycStatus.VERIFIED,
    )
    result = calculate_risk_rating(t)

    assert any(f.framework == "mifid_ii" for f in result.findings)
    assert result.risk_rating.severity >= RiskRating.HIGH.severity


def test_scenario_4_nbfc_lending_requiring_priority_sector_reporting_cites_rbi():
    t = _transaction(
        amount=4_200_000,
        transaction_type=TransactionType.LENDING,
        is_priority_sector=True,
        counterparty_kyc_status=KycStatus.VERIFIED,
    )
    result = calculate_risk_rating(t)

    assert any(f.framework == "rbi" and f.rule_id == "RBI-PSL-REPORTING" for f in result.findings)


def test_ambiguous_unknown_kyc_status_is_never_rated_below_medium():
    t = _transaction(counterparty_kyc_status=KycStatus.UNKNOWN)
    result = calculate_risk_rating(t)

    assert result.risk_rating.severity >= RiskRating.MEDIUM.severity
    assert "counterparty_kyc_status is unknown" in result.missing_facts
    assert result.assumptions  # AGENT-3.2: assumption stated, never silently "compliant"


# --- cross_reference_frameworks ---


def test_cross_reference_resolves_stricter_of_two_ceilings():
    chunks = [
        _chunk(Framework.BASEL_III, "9.1", "Exposure must not exceed 25% of Tier 1 capital."),
        _chunk(Framework.RBI, "4.1", "Exposure must not exceed 15% of capital funds for this counterparty class."),
    ]
    resolution = cross_reference_frameworks(chunks)

    assert resolution.stricter_thresholds["lowest_ceiling_pct"] == 15.0


def test_cross_reference_flags_genuine_conflict_between_floor_and_ceiling():
    chunks = [
        _chunk(Framework.BASEL_III, "6.1", "Banks must maintain at least 12% CET1 capital."),
        _chunk(Framework.RBI, "2.1", "Capital ratio must not exceed 10% for this exposure class."),
    ]
    resolution = cross_reference_frameworks(chunks)

    assert resolution.conflicts, "an unsatisfiable floor/ceiling pair across frameworks must be surfaced"


def test_cross_reference_single_framework_has_no_conflicts():
    chunks = [_chunk(Framework.RBI, "3.3", "Must not exceed USD 1,000,000 without escalation.")]
    resolution = cross_reference_frameworks(chunks)

    assert resolution.conflicts == []


# --- generate_citation_bundle ---


def test_generate_citation_bundle_prefers_exact_clause_match():
    findings = calculate_risk_rating(
        _transaction(
            amount=2_000_000,
            counterparty_kyc_status=KycStatus.NOT_VERIFIED,
            counterparty_jurisdiction_risk="high",
        )
    ).findings
    chunks = [
        _chunk(Framework.RBI, "3.1", "General CDD requirement."),
        _chunk(Framework.RBI, "3.3", "Cross-border transfer to non-KYC-verified entity threshold."),
    ]

    bundle = generate_citation_bundle(findings, chunks)

    rule_id = findings[0].rule_id
    assert bundle[rule_id].clause_id == "3.3"
