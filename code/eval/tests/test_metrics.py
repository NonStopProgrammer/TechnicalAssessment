from eval.metrics.citation_accuracy import citation_accuracy
from eval.metrics.ragas_runner import run_ragas
from eval.metrics.risk_rating_accuracy import risk_rating_accuracy


def test_citation_accuracy_full_match():
    result = citation_accuracy(["a#1@v1", "b#2@v1"], ["a#1@v1", "b#2@v1"])
    assert result.score == 1.0
    assert not result.missing and not result.unexpected


def test_citation_accuracy_partial_match():
    result = citation_accuracy(["a#1@v1"], ["a#1@v1", "b#2@v1"])
    assert result.score == 0.5
    assert result.missing == ["b#2@v1"]


def test_citation_accuracy_refusal_case_with_no_citations_scores_perfectly():
    result = citation_accuracy([], [])
    assert result.score == 1.0


def test_citation_accuracy_refusal_case_that_still_cited_something_scores_zero():
    result = citation_accuracy(["a#1@v1"], [])
    assert result.score == 0.0
    assert result.unexpected == ["a#1@v1"]


def test_risk_rating_accuracy_all_pass():
    cases = [
        {"transaction_id": "T1", "expected_min_rating": "HIGH", "actual_rating": "CRITICAL"},
        {"transaction_id": "T2", "expected_min_rating": "MEDIUM", "actual_rating": "MEDIUM"},
    ]
    result = risk_rating_accuracy(cases)
    assert result.score == 1.0
    assert result.mismatches == []


def test_risk_rating_accuracy_flags_below_floor():
    cases = [{"transaction_id": "T1", "expected_min_rating": "HIGH", "actual_rating": "LOW"}]
    result = risk_rating_accuracy(cases)
    assert result.score == 0.0
    assert result.mismatches


def test_ragas_runner_reports_unavailable_gracefully_when_not_installed():
    # This assertion holds whether or not `ragas` happens to be installed
    # in the current environment (requirements-full.txt, not requirements.txt):
    # either it's unavailable and skipped, or it ran and returned scores —
    # either way the call must not raise.
    result = run_ragas([{"question": "q", "answer": "a", "contexts": ["c"], "ground_truth": "g"}])
    assert isinstance(result.available, bool)
