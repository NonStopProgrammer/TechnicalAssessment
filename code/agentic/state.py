"""AGENT-2.1: typed state object. Every field here persists to the
LangGraph checkpoint at every node transition (AGENT-2.2) — that checkpoint
history *is* the audit trail for SEC-2.3/the Internal Auditor persona, so
nothing that matters is allowed to live only in a local variable inside a
node function.
"""

from typing import TypedDict

from shared.models.assessment import ComplianceAssessment
from shared.models.chunk import RetrievedChunk
from shared.models.transaction import TransactionPayload


class ComplianceGraphState(TypedDict, total=False):
    # Input
    request_id: str
    transaction: TransactionPayload

    # classify_input
    applicable_frameworks: list[str]
    redacted_input_for_audit: dict

    # retrieve
    retrieved_chunks: list[RetrievedChunk]

    # cross_reference
    cross_reference_by_framework: dict[str, list[str]]  # framework -> chunk_ids, JSON-safe for checkpointing
    conflicts: list[dict]
    stricter_thresholds: dict[str, float]

    # score_risk
    risk_rating: str
    rule_findings: list[dict]
    required_actions: list[dict]
    assumptions: list[str]
    missing_facts: list[str]

    # draft_assessment
    draft_narrative: str
    draft_key_points: list[str]
    draft_model_id: str
    draft_model_version: str
    draft_prompt_template_id: str
    draft_prompt_template_version: str

    # score_risk (citations) / verify_citations
    citations: list[dict]  # deduplicated Citation dicts
    citation_by_rule_id: dict[str, dict]  # rule_id -> Citation dict, for finalize's rule_triggers/required_actions
    citation_verification_passed: bool
    narrative_retry_count: int

    # confidence / human-in-the-loop
    confidence_score: float
    human_review_decision: str | None

    # control
    step_count: int
    status: str
    error: str | None

    # finalize
    final_assessment: ComplianceAssessment
