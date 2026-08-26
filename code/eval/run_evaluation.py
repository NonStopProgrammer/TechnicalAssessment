"""EVAL entrypoint: `python -m eval.run_evaluation` (from `code/`) runs the
full EVAL-1..EVAL-3 suite and writes a markdown + JSON report to
`eval/reports/`. Also called by `rag/dags/nightly_eval_dag.py` (OBS-2.1).
"""

import json
from pathlib import Path

from agentic.graph.build_graph import run_screening
from agentic.qa import answer_question
from agentic.tools.get_transaction_details import get_transaction_details, seed_transactions
from eval.metrics.citation_accuracy import citation_accuracy
from eval.metrics.ragas_runner import run_ragas
from eval.metrics.risk_rating_accuracy import risk_rating_accuracy
from eval.report_generator import EvaluationReport, QuestionResult
from rag.ingestion.pipeline import ingest_directory
from shared.config import get_settings
from shared.db.base import init_db
from shared.ids import utcnow

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "qa_ground_truth.json"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"

# EVAL-1.2 / assignment's own 4 reference transaction-screening scenarios.
REFERENCE_SCENARIOS = [
    {"transaction_id": "TXN-1001", "expected_min_rating": "HIGH"},
    {"transaction_id": "TXN-1002", "expected_min_rating": "MEDIUM"},
    {"transaction_id": "TXN-1003", "expected_min_rating": "HIGH"},
    {"transaction_id": "TXN-1004", "expected_min_rating": "MEDIUM"},
]


def _ensure_corpus_and_transactions() -> None:
    init_db()
    corpus_dir = get_settings().code_root / "rag" / "corpus" / "sample_documents"
    ingest_directory(corpus_dir)  # RAG-1.4: idempotent
    seed_transactions()


def run_full_evaluation() -> EvaluationReport:
    _ensure_corpus_and_transactions()
    qa_pairs = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    question_results: list[QuestionResult] = []
    ragas_samples: list[dict] = []
    model_id = model_version = "n/a"

    for pair in qa_pairs:
        answer = answer_question(query=pair["question"])
        actual_keys = [c.citation_key for c in answer.citations]
        accuracy = citation_accuracy(actual_keys, pair["expected_citation_keys"])

        if answer.provenance:
            model_id, model_version = answer.provenance.model_id, answer.provenance.model_version

        if pair["expects_refusal"]:
            # Either guardrail counts: RAG-4.6's relevance floor
            # ("insufficient_context") and LLM-4.5's topical rail
            # ("off_topic") are different mechanisms, but both represent
            # the system correctly declining rather than answering ungrounded.
            passed = answer.status in ("insufficient_context", "off_topic")
            failure_reason = None if passed else f"expected a refusal but got status '{answer.status}'"
        else:
            passed = accuracy.score >= 0.90
            failure_reason = None if passed else f"missing citations {accuracy.missing}, unexpected {accuracy.unexpected}"

        question_results.append(
            QuestionResult(
                id=pair["id"],
                question=pair["question"],
                framework=pair["framework"],
                difficulty=pair["difficulty"],
                expects_refusal=pair["expects_refusal"],
                generated_answer=answer.answer,
                generated_status=answer.status,
                expected_citation_keys=pair["expected_citation_keys"],
                actual_citation_keys=actual_keys,
                citation_score=accuracy.score,
                passed=passed,
                failure_reason=failure_reason,
            )
        )

        if answer.status == "answered":
            ragas_samples.append(
                {
                    "question": pair["question"],
                    "answer": answer.answer,
                    "contexts": [c.snippet for c in answer.citations] or [answer.answer],
                    "ground_truth": pair["ground_truth_answer"],
                }
            )

    risk_cases = []
    for scenario in REFERENCE_SCENARIOS:
        transaction = get_transaction_details(scenario["transaction_id"])
        assessment = run_screening(transaction, request_id=f"eval-{scenario['transaction_id']}")
        risk_cases.append({**scenario, "actual_rating": assessment.risk_rating.value})
    risk_result = risk_rating_accuracy(risk_cases)

    ragas_result = run_ragas(ragas_samples) if ragas_samples else None
    ragas_dict = (
        {
            "available": ragas_result.available,
            "scores": ragas_result.scores,
            "skipped_reason": ragas_result.skipped_reason,
            "failing_metrics": ragas_result.failing_metrics(),
        }
        if ragas_result
        else {"available": False, "skipped_reason": "no answered questions to evaluate"}
    )

    citation_scores = [r.citation_score for r in question_results]
    report = EvaluationReport(
        generated_at=utcnow().isoformat(),
        model_id=model_id,
        model_version=model_version,
        embedding_provider=get_settings().embedding_provider,
        question_results=question_results,
        risk_rating_score=risk_result.score,
        risk_rating_detail={
            "total": risk_result.total,
            "correct": risk_result.correct,
            "mismatches": risk_result.mismatches,
        },
        ragas=ragas_dict,
        citation_accuracy_mean=sum(citation_scores) / len(citation_scores) if citation_scores else 0.0,
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "latest.md").write_text(report.to_markdown(), encoding="utf-8")
    (REPORTS_DIR / "latest.json").write_text(report.to_json(), encoding="utf-8")

    return report


if __name__ == "__main__":
    evaluation_report = run_full_evaluation()
    print(evaluation_report.to_markdown())
    print(f"\nReports written to {REPORTS_DIR}")
