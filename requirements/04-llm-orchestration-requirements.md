# LLM Orchestration Layer Requirements

Covers rubric item **1A.3 LLM Orchestration Layer**. See `ADR-002-model-hosting-strategy.md` for
the self-hosted-vs-API trade-off and `10-technology-stack.md` for consolidated choices.

---

## LLM-1 — Foundation model selection

| ID | Requirement | Detail |
|---|---|---|
| LLM-1.1 | Open-weight models only, self-hosted by default | **Llama-3.1-8B-Instruct** (routing/classification tier) and **Llama-3.1-70B-Instruct** (generation tier), both Apache-class open-weight licenses, served via **vLLM**. Chosen over closed APIs primarily for `SEC-3` (no regulated data leaves FinServ's VPC) — see `ADR-002`. |
| LLM-1.2 | [PROPRIETARY] managed alternative, flagged | **AWS Bedrock** can host the *same* open-weight Llama models as a managed inference endpoint, trading self-hosting ops burden for a paid, AWS-operated service. This is not a different model choice, just a different hosting posture — the assignment's "no proprietary services without a flagged OSS alternative" is satisfied because the model itself stays open-weight either way, but Bedrock-as-a-service is called out here since it is a paid AWS offering. **[OSS ALTERNATIVE the prototype actually uses]: self-hosted vLLM.** |
| LLM-1.3 | Quantization for cost/latency | 70B tier served AWQ 4-bit quantized to fit commodity GPU nodes (see `06-infrastructure-nfr-requirements.md` cost model) with acceptable accuracy loss (validated against `EVAL-2` thresholds before promoting a quantized checkpoint to production). |
| LLM-1.4 | Model registry & pinning | Every deployed model has an explicit version pin (weights hash + quantization config) recorded in the same provenance block as `FR-5`; no silent "latest" resolution. |

## LLM-2 — Multi-model routing strategy

| ID | Requirement | Detail |
|---|---|---|
| LLM-2.1 | Router tier (small model) | Llama-3.1-8B handles: query intent classification (Q&A vs. screening vs. report), transaction-type classification (`FR-2` taxonomy), and a first-pass PII/sensitive-field scan before anything is logged. |
| LLM-2.2 | Generation tier (large model) | Llama-3.1-70B handles: final answer synthesis (`FR-1`), compliance assessment narrative (`FR-2`), report narrative (`FR-4`) — i.e., anything a human ultimately reads and acts on. |
| LLM-2.3 | Routing is deterministic where possible | Task-type routing (which tier handles which endpoint) is config-driven (`config/model_routing.yaml`), not LLM-decided, so behavior is predictable and auditable. Only within-tier model *selection under fallback* (LLM-2.4) is dynamic. |
| LLM-2.4 | Fallback chain & circuit breaker | Primary self-hosted model → secondary self-hosted smaller model on timeout/error → circuit breaker opens after N consecutive failures and returns a structured "assistant temporarily degraded" response. **No automatic fallback to an external SaaS API for any endpoint touching regulated document text or transaction data** — an external fallback, if ever added, requires an explicit non-sensitive-task allowlist and PII redaction pass first (`SEC-3`). |
| LLM-2.5 | Cost control | Per-request token budget enforced at the orchestration layer (hard cap on context + generation tokens); semantic response cache (**GPTCache**, open source) in front of the generation tier for repeated/near-duplicate queries. |

## LLM-3 — Prompt engineering framework

| ID | Requirement | Detail |
|---|---|---|
| LLM-3.1 | Versioned prompt templates | Per-task templates (`qa_answer`, `transaction_screening`, `regulatory_diff`, `report_narrative`) stored as version-controlled Jinja2 files, each with a semantic version; the version used is part of the `FR-5` provenance block. |
| LLM-3.2 | System prompt contract | Every template's system prompt fixes: role/scope ("answer only from provided regulatory context"), citation format (`RAG-6.1` key), refusal condition (`FR-1.5`), and output schema (for structured tasks, see `LLM-3.4`). |
| LLM-3.3 | Few-shot examples | Each template ships 2–4 curated few-shot examples covering: a well-cited answer, a correct refusal-for-insufficient-context, and (for screening) a correctly-flagged ambiguous case (`FR-2.6`). Examples are reviewed by a compliance SME before being frozen into a template version — this is a control point, not just prompt craft. |
| LLM-3.4 | Chain-of-thought for screening/report tasks, hidden from the end answer | `transaction_screening` and `report_narrative` templates elicit a scratchpad reasoning step (which frameworks apply → which clauses → risk factors → rating) that is logged for audit (`SEC-2`) but not shown verbatim to the end user, who sees the structured summary instead. |
| LLM-3.5 | Structured output enforcement | Screening/report outputs are constrained to a JSON schema (risk rating enum, citations array, required-actions array) via guided generation (vLLM's structured-output support / `outlines`), not just "please respond in JSON" — a hard requirement given `FR-2.3`/`FR-4.2` downstream parsing. |

## LLM-4 — Guardrails

| ID | Requirement | Detail |
|---|---|---|
| LLM-4.1 | Hallucination mitigation | Grounding is structural, not just prompted: the model only receives the re-ranked/compressed context (`RAG-4`) and is instructed to answer solely from it; `LLM-4.4` verifies compliance after the fact. |
| LLM-4.2 | Output schema validation | Every structured output (`LLM-3.5`) is validated against its Pydantic/JSON-schema on the way out; a validation failure triggers one bounded retry with the error fed back to the model, then falls back to `FR-1.5`-style graceful degradation. |
| LLM-4.3 | PII redaction | **Microsoft Presidio** (open source) scans transaction payloads and any free text before it is logged, cached, or included in a report export; detected PII (names, account numbers, national IDs) is redacted/tokenized in anything that isn't the immediate authorized response. |
| LLM-4.4 | Citation-verifier (domain-specific hallucination check) | A deterministic post-generation check confirms every citation key (`RAG-6.1`) in the answer resolves to a chunk actually present in the retrieved/re-ranked set for that request. Any citation that doesn't resolve is either stripped (with the corresponding claim flagged) or the whole response is rejected and regenerated once — this directly targets the "regulatory accuracy checks" requirement. |
| LLM-4.5 | Topical/scope rail | **NeMo Guardrails** (open source) constrains the assistant to compliance-domain queries; off-topic requests get a fixed decline rather than being forwarded to the LLM at all (cost control + reduces attack surface for prompt injection via unrelated content). |
| LLM-4.6 | Numeric-consistency guardrail | For `FR-4` report narratives specifically: any number the LLM states in prose is checked against the deterministically-computed aggregate it should match (`FR-4.3`); mismatches block report finalization rather than shipping a report with a hallucinated statistic. |
