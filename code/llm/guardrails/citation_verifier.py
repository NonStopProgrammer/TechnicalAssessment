"""LLM-4.4: citation-verifier — the domain-specific hallucination check.

Deterministically confirms every citation key an answer claims resolves to
a chunk actually present in the retrieved/re-ranked set for that request.
This is intentionally dumb string-set logic, not another LLM call: the
whole point is a check that cannot itself hallucinate.
"""

from dataclasses import dataclass, field


@dataclass
class CitationVerification:
    verified: list[str] = field(default_factory=list)
    unverified: list[str] = field(default_factory=list)

    @property
    def all_verified(self) -> bool:
        return not self.unverified


def verify_citations(citations_used: list[str], retrieved_citation_keys: set[str]) -> CitationVerification:
    verified = [key for key in citations_used if key in retrieved_citation_keys]
    unverified = [key for key in citations_used if key not in retrieved_citation_keys]
    return CitationVerification(verified=verified, unverified=unverified)


def strip_unverified_citations(answer: str, unverified: list[str]) -> str:
    """Policy A (LLM-4.4): strip the bad citation tag and flag the claim,
    rather than rejecting the whole answer. Used when at least one citation
    verified — a partially-grounded answer with a flagged gap is more
    useful to a Compliance Officer than a full regeneration for every miss.
    """
    flagged = answer
    for key in unverified:
        flagged = flagged.replace(key, f"{key} [UNVERIFIED CITATION — REMOVED]")
    return flagged
