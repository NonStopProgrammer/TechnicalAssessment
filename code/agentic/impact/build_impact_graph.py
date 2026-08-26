"""FR-3: regulatory change impact analysis.

Triggered by ingestion (RAG-1.5/FR-3.1), never by a user query. Reuses the
document registry + a deterministic clause diff (FR-3.2) rather than the
RAG retrieval pipeline — a version diff is a document-content comparison,
not a semantic search, so `search_regulations` would be the wrong tool
here even though AGENT-4 allows this graph to reuse RAG-pipeline pieces.
FR-3.4: output is always a review-queue row, never an auto-applied change.
"""

from functools import lru_cache
from typing import TypedDict

from langgraph.graph import END, StateGraph

from llm.prompts.registry import render_prompt
from llm.response_models import NarrativeOutput
from llm.structured_output import GenerationDegraded, generate_structured
from rag.chunking.clause_chunker import split_into_clauses
from rag.ingestion.parsers import parse_document
from shared.db.base import session_scope
from shared.db.models import DocumentRegistry, ImpactReviewItem
from shared.logging import get_logger

logger = get_logger(__name__)

# Reverse of agentic/graph/nodes.py::_applicable_frameworks — which
# transaction-screening types (FR-2's taxonomy) a framework's rules affect.
_FRAMEWORK_TRANSACTION_TYPES: dict[str, list[str]] = {
    "basel_iii": ["derivative_trade"],
    "mifid_ii": ["investment"],
    "rbi": ["cross_border_payment", "lending"],
}


class ImpactGraphState(TypedDict, total=False):
    new_doc_id: str
    superseded_doc_id: str | None
    changed_clauses: list[dict]
    affected_transaction_types: list[str]
    narrative: str
    key_points: list[str]


def diff_clauses(state: ImpactGraphState) -> dict:
    new_clauses = _load_clauses_by_id(state["new_doc_id"])
    superseded_doc_id = state.get("superseded_doc_id")

    if not superseded_doc_id:
        changed = [
            {"clause_id": cid, "old_text": None, "new_text": text, "change_type": "new_document"}
            for cid, text in new_clauses.items()
        ]
        return {"changed_clauses": changed}

    old_clauses = _load_clauses_by_id(superseded_doc_id)
    changed: list[dict] = []
    for clause_id, new_text in new_clauses.items():
        old_text = old_clauses.get(clause_id)
        if old_text is None:
            changed.append({"clause_id": clause_id, "old_text": None, "new_text": new_text, "change_type": "added"})
        elif old_text.strip() != new_text.strip():
            changed.append(
                {"clause_id": clause_id, "old_text": old_text, "new_text": new_text, "change_type": "modified"}
            )
    for clause_id, old_text in old_clauses.items():
        if clause_id not in new_clauses:
            changed.append({"clause_id": clause_id, "old_text": old_text, "new_text": None, "change_type": "removed"})

    return {"changed_clauses": changed}


def _load_clauses_by_id(doc_id: str) -> dict[str, str]:
    with session_scope() as db:
        row = db.get(DocumentRegistry, doc_id)
        source_uri = row.source_uri if row else None

    if not source_uri:
        return {}
    parsed = parse_document(source_uri)
    return {section.clause_id: section.text for section in split_into_clauses(parsed.raw_text)}


def map_affected_transaction_types(state: ImpactGraphState) -> dict:
    with session_scope() as db:
        row = db.get(DocumentRegistry, state["new_doc_id"])
        framework = row.framework if row else None
    return {"affected_transaction_types": _FRAMEWORK_TRANSACTION_TYPES.get(framework, [])}


def draft_narrative_and_enqueue(state: ImpactGraphState) -> dict:
    changed = state.get("changed_clauses", [])
    prompt = render_prompt(
        "regulatory_diff",
        new_doc_id=state["new_doc_id"],
        superseded_doc_id=state.get("superseded_doc_id"),
        changed_clauses=[{"clause_id": c["clause_id"], "summary": _summarize_change(c)} for c in changed],
    )

    narrative, key_points = f"{len(changed)} clause(s) changed; see changed_clauses for detail.", []
    try:
        generation = generate_structured(
            task="regulatory_diff_summary",
            template_id=prompt.template_id,
            template_version=prompt.version,
            system_prompt=prompt.system_prompt,
            user_prompt=prompt.user_prompt,
            response_model=NarrativeOutput,
        )
        narrative, key_points = generation.parsed.narrative, generation.parsed.key_points
    except GenerationDegraded as exc:
        logger.warning("agent.impact_narrative_degraded", error=str(exc))

    with session_scope() as db:
        db.add(
            ImpactReviewItem(
                new_doc_id=state["new_doc_id"],
                superseded_doc_id=state.get("superseded_doc_id"),
                changed_clauses=changed,
                affected_transaction_types=state.get("affected_transaction_types", []),
                status="pending_review",  # FR-3.4: human-in-the-loop, never auto-applied
            )
        )

    return {"narrative": narrative, "key_points": key_points}


def _summarize_change(c: dict) -> str:
    if c["change_type"] in ("added", "new_document"):
        return f"Clause {c['clause_id']} added: {c['new_text'][:200]}"
    if c["change_type"] == "removed":
        return f"Clause {c['clause_id']} removed (was: {c['old_text'][:200]})"
    return f"Clause {c['clause_id']} modified: was '{c['old_text'][:100]}', now '{c['new_text'][:100]}'"


def build_impact_graph():
    graph = StateGraph(ImpactGraphState)
    graph.add_node("diff_clauses", diff_clauses)
    graph.add_node("map_affected_transaction_types", map_affected_transaction_types)
    graph.add_node("draft_narrative_and_enqueue", draft_narrative_and_enqueue)

    graph.set_entry_point("diff_clauses")
    graph.add_edge("diff_clauses", "map_affected_transaction_types")
    graph.add_edge("map_affected_transaction_types", "draft_narrative_and_enqueue")
    graph.add_edge("draft_narrative_and_enqueue", END)

    return graph.compile()


@lru_cache
def get_impact_graph():
    return build_impact_graph()


def run_impact_scan(new_doc_id: str, superseded_doc_id: str | None) -> dict:
    graph = get_impact_graph()
    return graph.invoke({"new_doc_id": new_doc_id, "superseded_doc_id": superseded_doc_id})
