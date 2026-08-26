"""FR-1 fast path (AGENT-4): "Simple path may bypass the full agent graph
and call search_regulations + generation directly when no cross-
referencing/risk-scoring is needed" — the agent StateGraph's audit-trail
and retry machinery exist for AGENT-2.2's checkpoint-as-audit-trail need,
which a read-only regulatory question doesn't have.

Both `backend/app/services/qa_service.py` and
`mcp/fincompliance_mcp/server.py` call this one function rather than each
re-implementing FR-1, so there is exactly one FR-1 answer path.
"""

from dataclasses import dataclass, field

from agentic.tools.search_regulations import search_regulations
from llm.guardrails.citation_verifier import strip_unverified_citations, verify_citations
from llm.guardrails.topical_rail import FIXED_DECLINE_MESSAGE, get_topical_rail
from llm.prompts.registry import render_prompt
from llm.response_models import QaAnswerOutput
from llm.structured_output import GenerationDegraded, generate_structured
from shared.models.citation import Citation
from shared.models.provenance import ProvenanceBlock

INSUFFICIENT_CONTEXT_MESSAGE = "insufficient information in the indexed corpus"
DEGRADED_MESSAGE = "The assistant is temporarily degraded — please retry shortly."
MAX_QUERY_LENGTH = 2000  # FR-1.1


@dataclass
class QaAnswer:
    answer: str
    status: str  # "answered" | "insufficient_context" | "off_topic" | "degraded"
    citations: list[Citation] = field(default_factory=list)
    provenance: ProvenanceBlock | None = None


def answer_question(
    query: str,
    jurisdictions: list[str] | None = None,
    framework: str | None = None,
    as_of: str | None = None,
) -> QaAnswer:
    if not query or not query.strip():
        raise ValueError("query must not be empty")
    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError(f"query exceeds the {MAX_QUERY_LENGTH} character limit")

    if not get_topical_rail().is_in_scope(query):  # LLM-4.5
        return QaAnswer(answer=FIXED_DECLINE_MESSAGE, status="off_topic")

    retrieval = search_regulations(query=query, jurisdictions=jurisdictions, framework=framework)
    if not retrieval.has_usable_context:  # RAG-4.6 / RAG-7.4 -> FR-1.5
        return QaAnswer(answer=INSUFFICIENT_CONTEXT_MESSAGE, status="insufficient_context")

    prompt = render_prompt("qa_answer", query=query, chunks=[rc.chunk for rc in retrieval.chunks], as_of=as_of)
    try:
        generation = generate_structured(
            task="qa_answer",
            template_id=prompt.template_id,
            template_version=prompt.version,
            system_prompt=prompt.system_prompt,
            user_prompt=prompt.user_prompt,
            response_model=QaAnswerOutput,
        )
    except GenerationDegraded:
        return QaAnswer(answer=DEGRADED_MESSAGE, status="degraded")

    parsed: QaAnswerOutput = generation.parsed
    retrieved_keys = {rc.chunk.citation_key for rc in retrieval.chunks}
    verification = verify_citations(parsed.citations_used, retrieved_keys)  # LLM-4.4

    answer_text = parsed.answer
    if verification.unverified:
        answer_text = strip_unverified_citations(answer_text, verification.unverified)

    chunk_by_key = {rc.chunk.citation_key: rc.chunk for rc in retrieval.chunks}
    citations = [
        Citation(
            citation_key=key,
            doc_id=chunk_by_key[key].doc_id,
            clause_id=chunk_by_key[key].clause_id,
            version=chunk_by_key[key].version,
            framework=chunk_by_key[key].framework,
            title=chunk_by_key[key].doc_id,
            snippet=chunk_by_key[key].text[:280],
        )
        for key in verification.verified
        if key in chunk_by_key
    ]

    provenance = ProvenanceBlock(
        model_id=generation.raw_response.model_id,
        model_version=generation.raw_response.model_version,
        prompt_template_id=prompt.template_id,
        prompt_template_version=prompt.version,
        retrieved_chunk_ids=[rc.chunk.chunk_id for rc in retrieval.chunks],
    )
    return QaAnswer(answer=answer_text, status="answered", citations=citations, provenance=provenance)
