# Evaluation Framework Requirements

Covers rubric item **2C Evaluation Framework**. This doc specifies what the (later)
implementation must build; the framework itself (RAGAS) also powers `OBS-2`/`OBS-3` in
production.

---

## EVAL-1 — Ground-truth test dataset

| ID | Requirement | Detail |
|---|---|---|
| EVAL-1.1 | Size | 15–20 question-answer pairs with ground truth, per assignment requirement. |
| EVAL-1.2 | Coverage | Spans all 3 frameworks (Basel III, MiFID II, RBI) and includes: straightforward single-clause lookups, cross-framework questions, at least one "should refuse — insufficient context" case, and the 4 sample transaction-screening scenarios (`FR-2` reference test cases) reframed as QA pairs. |
| EVAL-1.3 | Ground truth provenance | Each pair's expected answer is hand-written from the actual source document text (not model-generated), with the exact citation key(s) (`RAG-6.1`) it should be graded against. |
| EVAL-1.4 | Format | Structured (JSON/CSV): `question`, `ground_truth_answer`, `expected_citation_keys[]`, `framework`, `difficulty`. |

## EVAL-2 — Metrics

| ID | Metric | What it measures | Tooling | Floor (release gate, `OBS-2.3`) |
|---|---|---|---|---|
| EVAL-2.1 | Faithfulness | Is the generated answer actually supported by the retrieved context (no unsupported claims)? | RAGAS | ≥ 0.85 |
| EVAL-2.2 | Answer relevance | Does the answer actually address the question asked? | RAGAS | ≥ 0.80 |
| EVAL-2.3 | Context precision | Of the retrieved chunks, how many were actually relevant/used? | RAGAS | ≥ 0.70 |
| EVAL-2.4 | Context recall | Of the ground-truth-relevant chunks, how many were retrieved? | RAGAS | ≥ 0.75 |
| EVAL-2.5 | Citation accuracy (custom, domain-specific) | Of the citation keys in the generated answer, what fraction match the expected citation key(s) in ground truth? | Custom (exact/overlap match against `EVAL-1.3`) | ≥ 0.90 — set stricter than the RAGAS floors because a wrong citation in a compliance answer is a materially worse failure than a slightly-off phrasing |
| EVAL-2.6 | Risk-rating accuracy (custom, for FR-2/2B scenarios only) | Does the agent's risk rating match the expected rating for the 4 reference transaction scenarios? | Custom (exact match against expected `LOW/MEDIUM/HIGH/CRITICAL`) | 4/4 on the assignment's own reference scenarios before any production consideration |

## EVAL-3 — Summary report

| ID | Requirement | Detail |
|---|---|---|
| EVAL-3.1 | Per-question breakdown | Score on every metric for every one of the 15–20 pairs, not just aggregates — needed for failure analysis. |
| EVAL-3.2 | Aggregate scores | Mean per metric, plus pass/fail against `EVAL-2` floors. |
| EVAL-3.3 | Failure analysis | For every pair scoring below floor on any metric: the actual retrieved chunks, the actual generated answer, and a short classification of the failure mode (e.g., "chunking split the threshold from its clause", "reranker demoted the correct chunk", "hallucinated citation") — this is what makes the report actionable rather than just a scoreboard. |
| EVAL-3.4 | Output format | Markdown report + machine-readable JSON (for `OBS-2.2` time-series ingestion later). |
| EVAL-3.5 | Reproducibility | Report records the exact model/prompt/index versions evaluated (same provenance fields as `FR-5`), so a score can always be tied to a specific system state. |
