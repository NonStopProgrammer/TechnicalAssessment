"""EVAL-2.6: risk-rating accuracy against the assignment's own 4 reference
transaction-screening scenarios — 4/4 required before any production
consideration.

Uses an "at least this severe" floor rather than exact-string equality,
because the assignment itself only pins scenario 1 to an exact
CRITICAL/HIGH expectation and leaves scenarios 2-4 to "expect <framework>
cited" (see requirements/02-functional-requirements.md's own reference
test cases) — grading those on exact-match against a rating this
implementation invented would be circular.
"""

from dataclasses import dataclass, field

from shared.enums import RiskRating


@dataclass
class RiskRatingAccuracyResult:
    total: int
    correct: int
    mismatches: list[dict] = field(default_factory=list)

    @property
    def score(self) -> float:
        return self.correct / self.total if self.total else 0.0


def risk_rating_accuracy(cases: list[dict]) -> RiskRatingAccuracyResult:
    """`cases`: [{"transaction_id", "expected_min_rating", "actual_rating"}, ...]"""
    mismatches = []
    correct = 0
    for case in cases:
        expected_floor = RiskRating(case["expected_min_rating"]).severity
        actual = RiskRating(case["actual_rating"]).severity
        if actual >= expected_floor:
            correct += 1
        else:
            mismatches.append(case)
    return RiskRatingAccuracyResult(total=len(cases), correct=correct, mismatches=mismatches)
