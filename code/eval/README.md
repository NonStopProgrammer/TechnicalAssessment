# Evaluation Framework

Implements `requirements/09-evaluation-framework-requirements.md` (EVAL-1..EVAL-3) and
rubric item 2C.

```
datasets/qa_ground_truth.json   EVAL-1: 20 QA pairs, all 3 frameworks + cross-framework +
                                 a should-refuse case + the 4 reference transaction scenarios
metrics/citation_accuracy.py    EVAL-2.5 (custom, floor 0.90)
metrics/risk_rating_accuracy.py EVAL-2.6 (custom, floor 4/4 on the reference scenarios)
metrics/ragas_runner.py         EVAL-2.1-2.4 (RAGAS; gracefully skipped without an LLM judge)
report_generator.py             EVAL-3: per-question breakdown + aggregates + failure analysis
run_evaluation.py               orchestrates all of the above end-to-end
```

## Run it

```bash
# from the code/ directory, with the venv active
python -m eval.run_evaluation
```

Writes `eval/reports/latest.md` and `latest.json`. The custom metrics (citation accuracy,
risk-rating accuracy) always run for real against whatever `LLM_GENERATION_PROVIDER` is
configured — with the MVP default (`local_stub`), citation accuracy is expected to score
very high since the stub is purely extractive (it cannot cite something it wasn't given).
RAGAS's LLM-judged metrics report `"available": false` under `local_stub` (there is no
model capable of judging faithfulness) and light up once `LLM_GENERATION_PROVIDER=vllm`
and `requirements-full.txt` are installed — see `eval/metrics/ragas_runner.py`'s docstring.

## Why citation accuracy and risk-rating accuracy matter more than RAGAS here

RAGAS measures groundedness/relevance in general; it does not know that "§9.1" is the
*correct* clause for a large-exposure question versus a merely-plausible-sounding one. For
a compliance assistant, a wrong citation is the failure mode that turns into a regulatory
incident (see `requirements/01-business-context-and-personas.md`'s Internal Auditor
persona) — which is why `EVAL-2.5`'s floor (0.90) is stricter than any RAGAS floor, and why
this framework treats the two custom metrics as load-bearing even when RAGAS is skipped.
