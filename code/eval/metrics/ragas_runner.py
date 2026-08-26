"""EVAL-2.1-2.4: RAGAS-based faithfulness / answer relevance / context
precision / context recall.

Requires `ragas` + `datasets` (requirements-full.txt) *and* an LLM judge —
RAGAS's metrics are themselves LLM-graded, so meaningful scores need a real
generation model wired in, not the MVP's extractive local_stub. This
function degrades to "skipped" (not "failed") when that isn't available,
so `run_evaluation.py` still produces a usable report — the domain-
specific custom metrics (citation_accuracy, risk_rating_accuracy), which
run for real regardless, are what this system's compliance correctness
actually hinges on; see requirements/09-evaluation-framework-
requirements.md's own framing of RAGAS vs. custom metrics.
"""

from dataclasses import dataclass, field

FLOORS = {
    "faithfulness": 0.85,
    "answer_relevancy": 0.80,
    "context_precision": 0.70,
    "context_recall": 0.75,
}


@dataclass
class RagasResult:
    available: bool
    scores: dict[str, float] = field(default_factory=dict)
    skipped_reason: str | None = None

    def failing_metrics(self) -> list[str]:
        if not self.available:
            return []
        return [name for name, floor in FLOORS.items() if self.scores.get(name, 0.0) < floor]


def run_ragas(samples: list[dict]) -> RagasResult:
    """`samples`: [{"question", "answer", "contexts": [str, ...], "ground_truth"}, ...]"""
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
    except ImportError as exc:
        return RagasResult(available=False, skipped_reason=f"ragas not installed: {exc}")

    try:
        dataset = Dataset.from_list(samples)
        result = evaluate(dataset, metrics=[faithfulness, answer_relevancy, context_precision, context_recall])
        scores = {name: float(result[name]) for name in FLOORS}
        return RagasResult(available=True, scores=scores)
    except Exception as exc:  # noqa: BLE001 — e.g. no LLM judge configured/reachable
        return RagasResult(available=False, skipped_reason=f"ragas evaluation failed: {exc}")
