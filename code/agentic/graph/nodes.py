"""AGENT-1.7 skeleton nodes: classify_input -> retrieve -> cross_reference ->
score_risk -> draft_assessment -> verify_citations -> finalize.

Each node takes the full state and returns only the partial update it
owns — LangGraph merges it in and persists the merged state at every
transition (AGENT-2.2's checkpoint-as-audit-trail).
"""

from agentic.state import ComplianceGraphState
from agentic.tools.calculate_risk_rating import RequiredAction, RuleFinding, calculate_risk_rating
from agentic.tools.cross_reference_frameworks import cross_reference_frameworks
from agentic.tools.generate_citation_bundle import generate_citation_bundle
from agentic.tools.search_regulations import search_regulations
from llm.guardrails.citation_verifier import verify_citations as verify_citation_keys
from llm.guardrails.pii_redaction import get_pii_redactor
from llm.prompts.registry import render_prompt
from llm.response_models import NarrativeOutput
from llm.structured_output import GenerationDegraded, generate_structured
from shared.config import get_settings
from shared.enums import AssessmentStatus, CustomerType, Framework, RiskRating, TransactionType
from shared.logging import get_logger
from shared.models.assessment import ComplianceAssessment, FrameworkConflict
from shared.models.assessment import RequiredAction as AssessmentRequiredAction
from shared.models.assessment import RuleTrigger
from shared.models.chunk import RetrievedChunk
from shared.models.citation import Citation
from shared.models.provenance import ProvenanceBlock
from shared.models.transaction import TransactionPayload

logger = get_logger(__name__)


def _step(state: ComplianceGraphState) -> int:
    return state.get("step_count", 0) + 1


def classify_input(state: ComplianceGraphState) -> dict:
    transaction = state["transaction"]
    frameworks = _applicable_frameworks(transaction)

    # LLM-2.1: router-tier first-pass PII scan before anything is logged.
    redactor = get_pii_redactor()
    redacted = redactor.redact_dict(transaction.model_dump(mode="json"))

    return {
        "applicable_frameworks": frameworks,
        "redacted_input_for_audit": redacted,
        "step_count": _step(state),
    }


def _applicable_frameworks(t: TransactionPayload) -> list[str]:
    """FR-2.2: identifies every framework a transaction touches, not just
    the most obvious one — deterministic, since `transaction_type` is
    already a structured input field with nothing left to classify.
    """
    frameworks: set[str] = set()
    if t.transaction_type == TransactionType.CROSS_BORDER_PAYMENT:
        frameworks.add(Framework.RBI.value)
    if t.transaction_type == TransactionType.DERIVATIVE_TRADE:
        frameworks.add(Framework.BASEL_III.value)
    if t.transaction_type == TransactionType.INVESTMENT and t.customer_type == CustomerType.RETAIL:
        frameworks.add(Framework.MIFID_II.value)
    if t.transaction_type == TransactionType.LENDING:
        frameworks.add(Framework.RBI.value)
    if t.customer_type == CustomerType.INTRA_GROUP:
        frameworks.add(Framework.BASEL_III.value)
    if not frameworks:
        frameworks.add(Framework.BASEL_III.value)  # conservative default: always check capital/exposure rules
    return sorted(frameworks)


def retrieve(state: ComplianceGraphState) -> dict:
    transaction = state["transaction"]
    query = _build_retrieval_query(transaction)

    all_chunks: list[RetrievedChunk] = []
    for framework in state.get("applicable_frameworks", []):
        result = search_regulations(query=query, jurisdictions=transaction.jurisdictions, framework=framework)
        all_chunks.extend(result.chunks)

    return {"retrieved_chunks": all_chunks, "step_count": _step(state)}


def _build_retrieval_query(t: TransactionPayload) -> str:
    parts = [t.transaction_type.value.replace("_", " "), t.instrument_type, t.customer_type.value]
    if t.counterparty_kyc_status:
        parts.append(f"KYC status {t.counterparty_kyc_status.value}")
    return " ".join(parts)


def cross_reference(state: ComplianceGraphState) -> dict:
    resolution = cross_reference_frameworks(state.get("retrieved_chunks", []))
    return {
        "cross_reference_by_framework": {
            framework: [rc.chunk.chunk_id for rc in chunks] for framework, chunks in resolution.by_framework.items()
        },
        "conflicts": [c.model_dump(mode="json") for c in resolution.conflicts],
        "stricter_thresholds": resolution.stricter_thresholds,
        "step_count": _step(state),
    }


def score_risk(state: ComplianceGraphState) -> dict:
    transaction = state["transaction"]
    retrieved_chunks = state.get("retrieved_chunks", [])

    assessment = calculate_risk_rating(transaction)
    citation_bundle = generate_citation_bundle(assessment.findings, retrieved_chunks)

    citation_by_rule_id = {rule_id: citation.model_dump(mode="json") for rule_id, citation in citation_bundle.items()}
    deduped_citations = list({c.citation_key: c for c in citation_bundle.values()}.values())

    return {
        "risk_rating": assessment.risk_rating.value,
        "rule_findings": [_finding_to_dict(f) for f in assessment.findings],
        "required_actions": [_action_to_dict(a) for a in assessment.required_actions],
        "assumptions": assessment.assumptions,
        "missing_facts": assessment.missing_facts,
        "citations": [c.model_dump(mode="json") for c in deduped_citations],
        "citation_by_rule_id": citation_by_rule_id,
        "step_count": _step(state),
    }


def _finding_to_dict(f: RuleFinding) -> dict:
    return {
        "rule_id": f.rule_id,
        "description": f.description,
        "framework": f.framework,
        "severity": f.severity.value,
        "preferred_clause_id": f.preferred_clause_id,
    }


def _action_to_dict(a: RequiredAction) -> dict:
    return {"action": a.action, "reason": a.reason, "rule_id": a.rule_id}


def draft_assessment(state: ComplianceGraphState) -> dict:
    """LLM-3.4: the narrative is generative; the rating and rules it
    explains were already computed by score_risk and are never
    re-decided here — see llm/response_models.py's design note.
    """
    prompt = render_prompt(
        "transaction_screening",
        risk_rating=state.get("risk_rating", RiskRating.LOW.value),
        facts=[{"rule_id": f["rule_id"], "description": f["description"]} for f in state.get("rule_findings", [])],
        assumptions=state.get("assumptions", []),
    )
    try:
        generation = generate_structured(
            task="transaction_screening_narrative",
            template_id=prompt.template_id,
            template_version=prompt.version,
            system_prompt=prompt.system_prompt,
            user_prompt=prompt.user_prompt,
            response_model=NarrativeOutput,
        )
        narrative_output: NarrativeOutput = generation.parsed
        return {
            "draft_narrative": narrative_output.narrative,
            "draft_key_points": narrative_output.key_points,
            "draft_model_id": generation.raw_response.model_id,
            "draft_model_version": generation.raw_response.model_version,
            "draft_prompt_template_id": prompt.template_id,
            "draft_prompt_template_version": prompt.version,
            "step_count": _step(state),
        }
    except GenerationDegraded as exc:
        # AGENT-3.1: narrative generation failed even after its bounded
        # retry — degrade rather than crash the run; the deterministic
        # rating/citations computed by score_risk are still returned.
        logger.warning("agent.draft_assessment_degraded", error=str(exc))
        return {
            "draft_narrative": "",
            "draft_key_points": [],
            "status": AssessmentStatus.DEGRADED.value,
            "error": str(exc),
            "step_count": _step(state),
        }


def verify_citations(state: ComplianceGraphState) -> dict:
    """LLM-4.4 applied defensively here (citations are built from the
    retrieved set by construction, so this mainly guards against a future
    regression) plus a narrative/rating consistency check that gives
    AGENT-3.4's retry loop something real to trigger on.
    """
    retrieved_keys = {rc.chunk.citation_key for rc in state.get("retrieved_chunks", [])}
    citation_keys_used = [c["citation_key"] for c in state.get("citations", [])]
    resolution = verify_citation_keys(citation_keys_used, retrieved_keys)

    narrative_consistent = _narrative_matches_rating(state.get("draft_narrative", ""), state.get("risk_rating", ""))
    retry_count = state.get("narrative_retry_count", 0)

    return {
        "citation_verification_passed": resolution.all_verified and narrative_consistent,
        "narrative_retry_count": retry_count if narrative_consistent else retry_count + 1,
        "step_count": _step(state),
    }


def _narrative_matches_rating(narrative: str, risk_rating: str) -> bool:
    if not narrative:
        return False
    upper = narrative.upper()
    other_ratings = {r.value for r in RiskRating if r.value != risk_rating}
    mentions_a_different_rating_only = any(r in upper for r in other_ratings) and risk_rating.upper() not in upper
    return not mentions_a_different_rating_only


def finalize(state: ComplianceGraphState) -> dict:
    settings = get_settings()
    citation_pass_rate = 1.0 if state.get("citation_verification_passed") else 0.5
    confidence = _compute_confidence(
        state.get("retrieved_chunks", []), citation_pass_rate, len(state.get("missing_facts", []))
    )

    if state.get("status") == AssessmentStatus.DEGRADED.value:
        status = AssessmentStatus.DEGRADED
    elif confidence < settings.agent_confidence_threshold:
        status = AssessmentStatus.NEEDS_REVIEW  # AGENT-2.4: human-in-the-loop interrupt fires in build_graph.py
    else:
        status = AssessmentStatus.COMPLETED

    citation_by_rule_id = state.get("citation_by_rule_id", {})
    all_citations = [Citation.model_validate(c) for c in state.get("citations", [])]

    rule_triggers = [
        RuleTrigger(
            rule_id=f["rule_id"],
            description=f["description"],
            framework=f["framework"],
            severity=RiskRating(f["severity"]),
            citations=_citations_for_rule(f["rule_id"], citation_by_rule_id),
        )
        for f in state.get("rule_findings", [])
    ]
    required_actions = [
        AssessmentRequiredAction(
            action=a["action"],
            reason=a["reason"],
            citations=_citations_for_rule(a.get("rule_id"), citation_by_rule_id),
        )
        for a in state.get("required_actions", [])
    ]

    assessment = ComplianceAssessment(
        transaction_id=state["transaction"].transaction_id,
        status=status,
        applicable_frameworks=state.get("applicable_frameworks", []),
        risk_rating=RiskRating(state.get("risk_rating", RiskRating.LOW.value)),
        rule_triggers=rule_triggers,
        required_actions=required_actions,
        citations=all_citations,
        assumptions=state.get("assumptions", []),
        missing_facts=state.get("missing_facts", []),
        conflicts=[FrameworkConflict.model_validate(c) for c in state.get("conflicts", [])],
        confidence_score=confidence,
        narrative=state.get("draft_narrative", ""),
        provenance=ProvenanceBlock(
            model_id=state.get("draft_model_id", "n/a"),
            model_version=state.get("draft_model_version", "n/a"),
            prompt_template_id=state.get("draft_prompt_template_id", "n/a"),
            prompt_template_version=state.get("draft_prompt_template_version", "n/a"),
            retrieved_chunk_ids=[rc.chunk.chunk_id for rc in state.get("retrieved_chunks", [])],
        ),
    )
    return {"final_assessment": assessment, "confidence_score": confidence, "status": status.value}


def _citations_for_rule(rule_id: str | None, citation_by_rule_id: dict[str, dict]) -> list[Citation]:
    if rule_id is None or rule_id not in citation_by_rule_id:
        return []
    return [Citation.model_validate(citation_by_rule_id[rule_id])]


def _compute_confidence(retrieved_chunks: list[RetrievedChunk], citation_pass_rate: float, missing_facts_count: int) -> float:
    """AGENT-3.3: confidence derives from retrieval relevance, citation-
    verifier pass rate, and completeness of required transaction fields.
    """
    if retrieved_chunks:
        average_score = sum(rc.final_score for rc in retrieved_chunks) / len(retrieved_chunks)
        relevance_component = min(1.0, average_score / 0.5)
    else:
        relevance_component = 0.0

    completeness_component = max(0.0, 1.0 - 0.25 * missing_facts_count)
    return round((relevance_component + citation_pass_rate + completeness_component) / 3, 3)


def degraded(state: ComplianceGraphState) -> dict:
    """AGENT-3.4 infinite-loop guard's terminal node: max step count
    exceeded, or an unrecoverable tool failure — return a structured
    degraded result instead of continuing to burn tokens/cost.
    """
    assessment = ComplianceAssessment(
        transaction_id=state["transaction"].transaction_id,
        status=AssessmentStatus.DEGRADED,
        risk_rating=RiskRating.MEDIUM,  # AGENT-3.2: never below MEDIUM when the assessment itself is incomplete
        confidence_score=0.0,
        narrative="Assessment could not be completed automatically and requires manual review.",
        missing_facts=["automated assessment did not complete — see error"],
    )
    return {"final_assessment": assessment, "status": AssessmentStatus.DEGRADED.value}
