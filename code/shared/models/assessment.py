"""FR-2.3-2.6 / AGENT-3 compliance assessment output — the payload every
screening request ultimately produces, whether via the fast path or the
full agent graph.
"""

from pydantic import BaseModel, Field

from shared.enums import AssessmentStatus, RiskRating
from shared.models.citation import Citation
from shared.models.provenance import ProvenanceBlock


class RuleTrigger(BaseModel):
    """The specific rule/threshold that drove (part of) the rating — FR-2.3."""

    rule_id: str
    description: str
    framework: str
    severity: RiskRating
    citations: list[Citation] = Field(default_factory=list)


class RequiredAction(BaseModel):
    action: str
    reason: str
    citations: list[Citation] = Field(default_factory=list)


class FrameworkConflict(BaseModel):
    """AGENT-3.5: two applicable rules conflict rather than merely differ in
    strictness — surfaced explicitly, never silently resolved.
    """

    description: str
    conflicting_rules: list[str]


class ComplianceAssessment(BaseModel):
    transaction_id: str | None = None
    status: AssessmentStatus = AssessmentStatus.COMPLETED
    applicable_frameworks: list[str] = Field(default_factory=list)
    risk_rating: RiskRating
    rule_triggers: list[RuleTrigger] = Field(default_factory=list)
    required_actions: list[RequiredAction] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)  # FR-2.6
    missing_facts: list[str] = Field(default_factory=list)  # AGENT-3.2
    conflicts: list[FrameworkConflict] = Field(default_factory=list)  # AGENT-3.5
    confidence_score: float = 1.0  # AGENT-3.3
    narrative: str = ""
    provenance: ProvenanceBlock | None = None
