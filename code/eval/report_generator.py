"""EVAL-3: summary report — per-question breakdown (not just aggregates),
aggregate scores, failure analysis, markdown + JSON output, and
reproducibility (the model/prompt/index versions evaluated).
"""

import json
from dataclasses import asdict, dataclass, field


@dataclass
class QuestionResult:
    id: str
    question: str
    framework: str
    difficulty: str
    expects_refusal: bool
    generated_answer: str
    generated_status: str
    expected_citation_keys: list[str]
    actual_citation_keys: list[str]
    citation_score: float
    passed: bool
    failure_reason: str | None = None


@dataclass
class EvaluationReport:
    generated_at: str
    model_id: str
    model_version: str
    embedding_provider: str
    question_results: list[QuestionResult] = field(default_factory=list)
    risk_rating_score: float = 0.0
    risk_rating_detail: dict = field(default_factory=dict)
    ragas: dict = field(default_factory=dict)
    citation_accuracy_mean: float = 0.0

    def to_summary_dict(self) -> dict:
        failing = []
        if self.citation_accuracy_mean < 0.90:
            failing.append("citation_accuracy")
        if self.risk_rating_score < 1.0:
            failing.append("risk_rating_accuracy")
        failing += self.ragas.get("failing_metrics", [])
        return {
            "citation_accuracy_mean": self.citation_accuracy_mean,
            "risk_rating_score": self.risk_rating_score,
            "ragas_available": self.ragas.get("available", False),
            "failing_metrics": failing,
        }

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)

    def to_markdown(self) -> str:
        lines = [
            "# Evaluation Report",
            "",
            f"- Generated: {self.generated_at}",
            f"- Model: {self.model_id} ({self.model_version})",
            f"- Embedding provider: {self.embedding_provider}",
            "",
            "## Aggregate scores",
            f"- Citation accuracy (mean): {self.citation_accuracy_mean:.3f} — floor 0.90 (EVAL-2.5)",
            f"- Risk-rating accuracy: {self.risk_rating_score:.3f} "
            f"({self.risk_rating_detail.get('correct', 0)}/{self.risk_rating_detail.get('total', 0)}) — floor 4/4 (EVAL-2.6)",
        ]
        if self.ragas.get("available"):
            for name, score in self.ragas.get("scores", {}).items():
                lines.append(f"- RAGAS {name}: {score:.3f}")
        else:
            lines.append(f"- RAGAS metrics: skipped ({self.ragas.get('skipped_reason', 'unavailable')})")

        lines += [
            "",
            "## Per-question breakdown",
            "",
            "| ID | Difficulty | Passed | Citation score | Notes |",
            "|---|---|---|---|---|",
        ]
        for result in self.question_results:
            status = "PASS" if result.passed else "FAIL"
            lines.append(f"| {result.id} | {result.difficulty} | {status} | {result.citation_score:.2f} | {result.failure_reason or ''} |")

        failures = [r for r in self.question_results if not r.passed]
        if failures:
            lines += ["", "## Failure analysis"]
            for result in failures:
                lines += [
                    f"### {result.id}: {result.question}",
                    f"- Generated status: `{result.generated_status}`",
                    f"- Generated answer: {result.generated_answer}",
                    f"- Expected citations: {result.expected_citation_keys}",
                    f"- Actual citations: {result.actual_citation_keys}",
                    f"- Failure reason: {result.failure_reason}",
                    "",
                ]

        if self.risk_rating_detail.get("mismatches"):
            lines += ["## Risk-rating mismatches", ""]
            for mismatch in self.risk_rating_detail["mismatches"]:
                lines.append(f"- `{mismatch}`")

        return "\n".join(lines)
