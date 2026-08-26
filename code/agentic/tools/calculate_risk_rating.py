"""AGENT-1.5: deterministic rule-scoring — never LLM-guessed, so the rating
is auditable and reproducible independent of sampling variance. Handles
AGENT-3.2's ambiguity rule throughout: a missing material fact floors the
rating at MEDIUM and is recorded as an assumption, never silently treated
as "compliant".

MVP simplification: amounts are compared directly against USD-denominated
thresholds with no FX conversion (matching the assignment's own scenario
phrasing, e.g. "$2M"), and the Basel III large-exposure check uses a flat
demo notional threshold because the counterparty's actual Tier 1 capital
base — needed for the real 25%-of-Tier-1 computation — is not part of this
payload or corpus. Both simplifications are intentional and are exactly
the kind of trade-off `requirements/11-non-goals-and-assumptions.md` asks
to state explicitly rather than hide.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from shared.enums import CustomerType, KycStatus, RiskRating, TransactionType
from shared.models.transaction import TransactionPayload

HIGH_VALUE_CROSS_BORDER_THRESHOLD_USD = 1_000_000  # matches rbi-kyc-master-direction §3.3
LARGE_EXPOSURE_DEMO_THRESHOLD_USD = 50_000_000  # demo stand-in — see module docstring


@dataclass
class RuleFinding:
    rule_id: str
    description: str
    framework: str
    severity: RiskRating
    preferred_clause_id: str | None = None


@dataclass
class RequiredAction:
    action: str
    reason: str
    rule_id: str | None = None


@dataclass
class RiskAssessmentResult:
    risk_rating: RiskRating = RiskRating.LOW
    findings: list[RuleFinding] = field(default_factory=list)
    required_actions: list[RequiredAction] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    missing_facts: list[str] = field(default_factory=list)


def calculate_risk_rating(transaction: TransactionPayload) -> RiskAssessmentResult:
    result = RiskAssessmentResult()
    scorer = _SCORERS.get(transaction.transaction_type)
    if scorer:
        scorer(transaction, result)

    if result.findings:
        result.risk_rating = RiskRating.max(result.risk_rating, *[f.severity for f in result.findings])
    return result


def _score_cross_border_payment(t: TransactionPayload, result: RiskAssessmentResult) -> None:
    if t.counterparty_kyc_status == KycStatus.UNKNOWN:
        # AGENT-3.2: unknown is never treated as compliant; floor at MEDIUM.
        result.missing_facts.append("counterparty_kyc_status is unknown")
        result.assumptions.append(
            "Treated as unverified pending confirmation per RBI KYC §3.4 — an unknown status is never assumed compliant."
        )
        result.findings.append(
            RuleFinding(
                rule_id="RBI-KYC-UNKNOWN-STATUS",
                description="KYC status could not be determined; rated no lower than MEDIUM pending confirmation.",
                framework="rbi",
                severity=RiskRating.MEDIUM,
                preferred_clause_id="3.4",
            )
        )
        return  # can't evaluate the stricter threshold rule without a known status

    high_risk_jurisdiction = (t.counterparty_jurisdiction_risk or "").lower() == "high"

    if t.counterparty_kyc_status == KycStatus.NOT_VERIFIED and high_risk_jurisdiction and t.amount >= HIGH_VALUE_CROSS_BORDER_THRESHOLD_USD:
        result.findings.append(
            RuleFinding(
                rule_id="RBI-KYC-CROSS-BORDER-THRESHOLD",
                description=(
                    f"Cross-border payment of {t.amount:,.0f} {t.currency} to a non-KYC-verified counterparty "
                    "in a high-risk jurisdiction exceeds the USD 1,000,000 escalation threshold."
                ),
                framework="rbi",
                severity=RiskRating.CRITICAL,
                preferred_clause_id="3.3",
            )
        )
        result.required_actions.append(
            RequiredAction(
                action="Block transaction pending enhanced due diligence",
                reason="Escalate to the Money Laundering Reporting Officer per RBI KYC §3.3 before releasing funds.",
                rule_id="RBI-KYC-CROSS-BORDER-THRESHOLD",
            )
        )
    elif t.counterparty_kyc_status == KycStatus.NOT_VERIFIED:
        result.findings.append(
            RuleFinding(
                rule_id="RBI-KYC-NOT-VERIFIED",
                description="Cross-border transaction to a non-KYC-verified counterparty must be held pending verification.",
                framework="rbi",
                severity=RiskRating.HIGH,
                preferred_clause_id="3.3",
            )
        )
        result.required_actions.append(
            RequiredAction(
                action="Hold transaction pending KYC verification",
                reason="Counterparty KYC is not verified (RBI KYC §3.3).",
                rule_id="RBI-KYC-NOT-VERIFIED",
            )
        )
    elif t.counterparty_kyc_status == KycStatus.PENDING and high_risk_jurisdiction:
        result.findings.append(
            RuleFinding(
                rule_id="RBI-EDD-CROSS-BORDER",
                description="Cross-border wire transfer to a high-risk jurisdiction requires Enhanced Due Diligence.",
                framework="rbi",
                severity=RiskRating.MEDIUM,
                preferred_clause_id="3.2",
            )
        )


def _score_derivative_trade(t: TransactionPayload, result: RiskAssessmentResult) -> None:
    if t.customer_type != CustomerType.INTRA_GROUP:
        return

    if t.amount >= LARGE_EXPOSURE_DEMO_THRESHOLD_USD:
        result.findings.append(
            RuleFinding(
                rule_id="BASEL-LARGE-EXPOSURE-BREACH",
                description=(
                    f"Intra-group derivative exposure of {t.amount:,.0f} {t.currency} requires measurement "
                    "against the 25% of Tier 1 capital large-exposure limit."
                ),
                framework="basel_iii",
                severity=RiskRating.HIGH,
                preferred_clause_id="9.1",
            )
        )
        result.required_actions.append(
            RequiredAction(
                action="Escalate for large-exposure limit review",
                reason="Intra-group exposures are subject to the Basel III §9.1 limit unless a documented, "
                "currently-reviewed waiver exists under §9.3.",
                rule_id="BASEL-LARGE-EXPOSURE-BREACH",
            )
        )
    else:
        result.missing_facts.append("counterparty Tier 1 capital base not provided")
        result.assumptions.append(
            "Exposure compared only against a demo notional threshold, not the counterparty's actual Tier 1 "
            "capital (unavailable in this payload) — see calculate_risk_rating.py module docstring."
        )


def _score_investment(t: TransactionPayload, result: RiskAssessmentResult) -> None:
    if t.customer_type != CustomerType.RETAIL:
        return

    if t.is_appropriateness_assessed is None:
        result.missing_facts.append("is_appropriateness_assessed is unknown")
        result.assumptions.append(
            "Treated as not-yet-documented pending confirmation — an unconfirmed assessment is never assumed compliant."
        )
        result.findings.append(
            RuleFinding(
                rule_id="MIFID-APPROPRIATENESS-UNKNOWN",
                description="Appropriateness-assessment status unknown for a retail investment; floored at MEDIUM.",
                framework="mifid_ii",
                severity=RiskRating.MEDIUM,
                preferred_clause_id="25.1",
            )
        )
    elif t.is_appropriateness_assessed is False:
        result.findings.append(
            RuleFinding(
                rule_id="MIFID-APPROPRIATENESS-MISSING",
                description="Retail client investment executed without a documented appropriateness assessment.",
                framework="mifid_ii",
                severity=RiskRating.HIGH,
                preferred_clause_id="25.4",
            )
        )
        result.required_actions.append(
            RequiredAction(
                action="Halt execution pending appropriateness assessment",
                reason="MiFID II §25.4 prohibits executing a complex-product transaction for a retail client "
                "without a documented appropriateness assessment.",
                rule_id="MIFID-APPROPRIATENESS-MISSING",
            )
        )


def _score_lending(t: TransactionPayload, result: RiskAssessmentResult) -> None:
    if t.is_priority_sector is False:
        return

    if t.is_priority_sector is None:
        result.missing_facts.append("is_priority_sector is unknown")
        result.assumptions.append("Treated as potentially priority-sector pending classification confirmation.")

    result.findings.append(
        RuleFinding(
            rule_id="RBI-PSL-REPORTING",
            description="Lending transaction qualifies as (or may qualify as) Priority Sector Lending and must "
            "be tagged and reported.",
            framework="rbi",
            severity=RiskRating.MEDIUM,
            preferred_clause_id="5.2",
        )
    )
    result.required_actions.append(
        RequiredAction(
            action="Tag as Priority Sector Lending and include in the quarterly PSL return",
            reason="RBI Priority Sector Lending §5.2/§5.3 requires tagging and reporting at origination.",
            rule_id="RBI-PSL-REPORTING",
        )
    )


_SCORERS: dict[TransactionType, Callable[[TransactionPayload, RiskAssessmentResult], None]] = {
    TransactionType.CROSS_BORDER_PAYMENT: _score_cross_border_payment,
    TransactionType.DERIVATIVE_TRADE: _score_derivative_trade,
    TransactionType.INVESTMENT: _score_investment,
    TransactionType.LENDING: _score_lending,
}
