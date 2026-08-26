# Observability Requirements

Covers rubric item **1B.3 Observability**.

---

## OBS-1 — Monitoring stack for LLM performance

| ID | Requirement | Detail |
|---|---|---|
| OBS-1.1 | Infra metrics | **Prometheus** + **Grafana** (open source): GPU utilization/memory (DCGM exporter), pod autoscaling events, request queue depth (feeds `INFRA-2.2`), service latency histograms. |
| OBS-1.2 | LLM-specific tracing | **Langfuse** (open source, self-hosted): per-request trace of prompt template + version, retrieved chunks, model tier used, tokens in/out, latency, and cost-per-request — this is the same data backing `FR-5`/`SEC-2.3`, surfaced for operational dashboards rather than audit lookup. |
| OBS-1.3 | Dashboards | Latency (P50/P95 vs. `INFRA-4` SLA), token usage & cost trend (vs. `06-infrastructure-nfr-requirements.md` budget), cache hit rate (`LLM-2.5`), guardrail trigger rate (`LLM-4` — a rising rate is itself a signal worth watching, not just a safety net). |
| OBS-1.4 | Alerting | Paged on: SLA breach (sustained P95 over threshold), cost budget alarm (`INFRA-3`), circuit breaker open (`LLM-2.4`), GPU node pool at capacity ceiling with queue growing (early warning before users see latency). |

## OBS-2 — Evaluation pipeline (automated quality scoring)

| ID | Requirement | Detail |
|---|---|---|
| OBS-2.1 | Nightly regression eval | Airflow DAG runs the `09-evaluation-framework-requirements.md` RAGAS suite against the fixed ground-truth set on every model/prompt/index version change, and nightly regardless, to catch silent regressions (e.g., an ingestion change that degrades chunk quality). |
| OBS-2.2 | Score history | Faithfulness / answer relevance / context precision / context recall / citation accuracy scores stored time-series (not just latest run) so a regression shows as a trend break, not a single bad number. |
| OBS-2.3 | Gate on deploy | A model/prompt/index change that drops any `EVAL-2` metric below its configured floor blocks promotion to production — evaluation is a release gate, not a report generated after the fact. |
| OBS-2.4 | Human sample review | A random 2% sample of production responses queued weekly for a compliance SME spot-check, closing the loop between automated metrics and actual domain correctness (RAGAS measures groundedness/relevance, not regulatory correctness — a SME is still required for the latter). |

## OBS-3 — Drift detection for retrieval relevance over time

| ID | Requirement | Detail |
|---|---|---|
| OBS-3.1 | Fixed benchmark query set | The same `EVAL-1` question set is re-run against the *current* index on a schedule; recall@k and re-ranker top-1 relevance are tracked over time as the corpus grows (200+ new circulars/year is exactly the condition that can silently dilute retrieval quality if unmonitored). |
| OBS-3.2 | Corpus-growth-aware alerting | Alert when recall@k on the fixed set drops more than a configured delta between two consecutive corpus versions — flags whether chunking/embedding assumptions (`RAG-2`, `RAG-3`) are holding up as the index scales past the initial 5-document prototype. |
| OBS-3.3 | Embedding/model deprecation handling | When `RAG-3.1`'s embedding model is upgraded, the full corpus must be re-embedded and validated against `OBS-3.1`'s benchmark *before* cutover (blue/green collection swap in Qdrant), never a partial re-embed left half-migrated. |
| OBS-3.4 | Query log mining | Anonymized query patterns reviewed periodically to find recurring `FR-1.5`/no-answer cases — a cluster of "insufficient information" responses on the same topic is a signal to prioritize that document/framework for ingestion, closing the loop from usage back to `RAG-1` ingestion priorities. |
