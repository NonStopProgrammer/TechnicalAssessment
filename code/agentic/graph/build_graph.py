"""AGENT-1.7: fixed-skeleton graph wiring — a bounded state machine, not
open-ended ReAct-style planning, because predictability and auditability
outweigh flexibility for a compliance decision tool (see ADR-003).

`verify_citations` has one conditional edge back to `draft_assessment`
(a bounded, single retry when the drafted narrative doesn't match the
deterministic rating — see nodes.py::_narrative_matches_rating) and one to
a terminal `degraded` node once AGENT_MAX_STEPS is exceeded (AGENT-3.4's
infinite-loop guard). Every other edge is a straight line.

MVP simplification of AGENT-2.4: a low-confidence result is returned with
`status=NEEDS_REVIEW` on a fully-computed ComplianceAssessment rather than
literally pausing the graph via LangGraph's dynamic `interrupt()` — the
Compliance Officer still gets a clear "this needs a human look" signal,
without this MVP also having to stand up a resume-the-paused-run API. A
true `interrupt()`/`Command(resume=...)` pause is the natural production
upgrade, using the same Postgres checkpointer already wired for AGENT-2.2.
"""

from functools import lru_cache

from langgraph.graph import END, StateGraph

from agentic.graph import nodes
from agentic.graph.checkpointer import get_checkpointer
from agentic.state import ComplianceGraphState
from shared.config import get_settings
from shared.models.assessment import ComplianceAssessment
from shared.models.transaction import TransactionPayload

MAX_NARRATIVE_RETRIES = 1


def _route_after_verify(state: ComplianceGraphState) -> str:
    settings = get_settings()
    if state.get("step_count", 0) >= settings.agent_max_steps:
        return "degraded"
    if not state.get("citation_verification_passed") and state.get("narrative_retry_count", 0) <= MAX_NARRATIVE_RETRIES:
        return "retry_draft"
    return "finalize"


def build_compliance_graph():
    graph = StateGraph(ComplianceGraphState)

    graph.add_node("classify_input", nodes.classify_input)
    graph.add_node("retrieve", nodes.retrieve)
    graph.add_node("cross_reference", nodes.cross_reference)
    graph.add_node("score_risk", nodes.score_risk)
    graph.add_node("draft_assessment", nodes.draft_assessment)
    graph.add_node("verify_citations", nodes.verify_citations)
    graph.add_node("finalize", nodes.finalize)
    graph.add_node("degraded", nodes.degraded)

    graph.set_entry_point("classify_input")
    graph.add_edge("classify_input", "retrieve")
    graph.add_edge("retrieve", "cross_reference")
    graph.add_edge("cross_reference", "score_risk")
    graph.add_edge("score_risk", "draft_assessment")
    graph.add_edge("draft_assessment", "verify_citations")
    graph.add_conditional_edges(
        "verify_citations",
        _route_after_verify,
        {"retry_draft": "draft_assessment", "finalize": "finalize", "degraded": "degraded"},
    )
    graph.add_edge("finalize", END)
    graph.add_edge("degraded", END)

    return graph.compile(checkpointer=get_checkpointer())


@lru_cache
def get_compliance_graph():
    return build_compliance_graph()


def run_screening(transaction: TransactionPayload, request_id: str) -> ComplianceAssessment:
    graph = get_compliance_graph()
    config = {"configurable": {"thread_id": request_id}}
    try:
        result = graph.invoke(
            {"transaction": transaction, "request_id": request_id, "step_count": 0}, config=config
        )
        return result["final_assessment"]
    except Exception as exc:  # noqa: BLE001 — AGENT-3.1: never let a tool/graph crash reach the API layer
        return nodes.degraded({"transaction": transaction, "error": str(exc)})["final_assessment"]
