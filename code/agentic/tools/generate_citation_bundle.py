"""AGENT-1.6: formats the final citation list attached to an assessment,
matching each rule finding to the most specific retrieved chunk available
(preferring an exact clause match over "just cite the framework").
"""

from agentic.tools.calculate_risk_rating import RuleFinding
from shared.models.chunk import RetrievedChunk
from shared.models.citation import Citation


def generate_citation_bundle(
    findings: list[RuleFinding], retrieved_chunks: list[RetrievedChunk]
) -> dict[str, Citation]:
    by_framework: dict[str, list[RetrievedChunk]] = {}
    for retrieved in retrieved_chunks:
        by_framework.setdefault(retrieved.chunk.framework.value, []).append(retrieved)

    citations: dict[str, Citation] = {}
    for finding in findings:
        candidates = by_framework.get(finding.framework, [])
        if not candidates:
            continue
        match = next((c for c in candidates if c.chunk.clause_id == finding.preferred_clause_id), candidates[0])
        citations[finding.rule_id] = Citation(
            citation_key=match.chunk.citation_key,
            doc_id=match.chunk.doc_id,
            clause_id=match.chunk.clause_id,
            version=match.chunk.version,
            framework=match.chunk.framework,
            title=match.chunk.doc_id,
            snippet=match.chunk.text[:280],
        )
    return citations
