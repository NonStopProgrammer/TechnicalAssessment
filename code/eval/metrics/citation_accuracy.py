"""EVAL-2.5: custom, domain-specific metric — of the citation keys in the
generated answer, what fraction match the expected citation key(s)? Set
stricter (0.90) than the RAGAS floors because a wrong citation in a
compliance answer is a materially worse failure than a slightly-off
phrasing RAGAS's semantic metrics would tolerate.
"""

from dataclasses import dataclass, field

FLOOR = 0.90


@dataclass
class CitationAccuracyResult:
    score: float
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)


def citation_accuracy(actual_citation_keys: list[str], expected_citation_keys: list[str]) -> CitationAccuracyResult:
    if not expected_citation_keys:
        # A refusal case (EVAL-1.2): correct iff the answer also cited nothing.
        return CitationAccuracyResult(score=1.0 if not actual_citation_keys else 0.0, unexpected=list(actual_citation_keys))

    actual_set, expected_set = set(actual_citation_keys), set(expected_citation_keys)
    matched = sorted(actual_set & expected_set)
    missing = sorted(expected_set - actual_set)
    unexpected = sorted(actual_set - expected_set)
    return CitationAccuracyResult(score=len(matched) / len(expected_set), matched=matched, missing=missing, unexpected=unexpected)
