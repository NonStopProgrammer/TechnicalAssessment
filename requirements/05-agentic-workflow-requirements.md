# Agentic Workflow Requirements

Covers rubric item **1A.4 Agentic Workflow Design** and implementation target **2B**. See
`ADR-003-orchestration-layer-build-vs-buy.md` for the framework choice rationale.

---

## AGENT-1 — Agent design & tools

The **Compliance Assessment Agent** is the primary agent: given a transaction description or a
regulatory question requiring cross-referencing, it plans and executes the retrieval/reasoning
steps needed to produce a grounded compliance assessment.

| ID | Requirement | Detail |
|---|---|---|
| AGENT-1.1 | Framework | **LangGraph** (open source). Chosen over CrewAI/AutoGen because it models the workflow as an explicit state graph with typed state, not a free-form multi-agent conversation — this is directly what `SEC-2` audit-trail and `AGENT-2` state-persistence requirements need. Full comparison in `ADR-003`. |
| AGENT-1.2 | Tool: `search_regulations(query, jurisdiction?, framework?)` | Wraps the RAG pipeline (`RAG-4`); returns re-ranked, cited chunks. |
| AGENT-1.3 | Tool: `get_transaction_details(transaction_id)` | Fetches the full transaction payload from the transaction data store (mocked/seeded in the prototype; a real core-banking integration in production). |
| AGENT-1.4 | Tool: `cross_reference_frameworks(regulation_hits)` | Given retrieval hits spanning >1 framework, resolves overlaps/conflicts (e.g., a stricter of two applicable thresholds) rather than concatenating them naively — this is the tool that directly answers the assignment's "cross-regulation complexity" pain point. |
| AGENT-1.5 | Tool: `calculate_risk_rating(factors)` | Deterministic rule-scoring function (not LLM-guessed) that maps extracted risk factors (KYC status, jurisdiction risk tier, amount vs. threshold, instrument complexity) to `LOW/MEDIUM/HIGH/CRITICAL` per `FR-2.3` — keeps the rating auditable and reproducible independent of LLM sampling variance. |
| AGENT-1.6 | Tool: `generate_citation_bundle(chunk_ids)` | Formats the final citation list (`RAG-6.1` keys → human-readable references) attached to the assessment. |
| AGENT-1.7 | Planning style | Fixed-skeleton graph (not open-ended ReAct-style free planning): `classify_input → retrieve → cross_reference → score_risk → draft_assessment → verify_citations → finalize`. A bounded skeleton is preferred over free planning for this domain — predictability and auditability outweigh flexibility for a compliance decision tool (an explicit trade-off, see `ADR-003`). |

## AGENT-2 — State management

| ID | Requirement | Detail |
|---|---|---|
| AGENT-2.1 | Typed state object | LangGraph state carries: input, classified intent, retrieved chunks per step, cross-reference resolution, computed risk factors, draft assessment, verification results — every field persists to the audit log, not just the final answer. |
| AGENT-2.2 | Checkpointing | LangGraph's Postgres-backed checkpointer persists state at every node transition. This *is* the audit trail for `SEC-2`/Internal Auditor persona — no separate logging pipeline needs to reconstruct "what did the agent see and decide", it's the checkpoint history. |
| AGENT-2.3 | Resumability | A failed run can resume from its last successful checkpoint rather than restarting (relevant once tool calls hit external systems with side effects, e.g., a future ticketing integration). |
| AGENT-2.4 | Human-in-the-loop interrupt point | Graph supports pausing before `finalize` when confidence is below threshold (`AGENT-3.3`), surfacing to a Compliance Officer for review rather than auto-finalizing a low-confidence assessment. |

## AGENT-3 — Error handling & ambiguity

| ID | Requirement | Detail |
|---|---|---|
| AGENT-3.1 | Tool failure | Each tool call wrapped with retry (bounded, exponential backoff) + typed exception → on exhaustion, the node transitions to a `degraded` state rather than crashing the graph run. |
| AGENT-3.2 | Ambiguous/insufficient transaction info (explicit rubric requirement for 2B) | When required fields for a confident assessment are missing (e.g., counterparty jurisdiction unknown), the agent does not guess: it returns a partial assessment explicitly listing the missing facts needed, at a capped risk rating floor (never rated below `MEDIUM` when material facts are missing — "unknown" is not "safe"). |
| AGENT-3.3 | Confidence scoring | Each assessment carries a confidence score derived from: retrieval relevance scores (`RAG-4.6`), citation-verifier pass rate (`LLM-4.4`), and completeness of required transaction fields. Below a configured threshold, `AGENT-2.4`'s human-in-the-loop interrupt fires. |
| AGENT-3.4 | Infinite-loop guard | Max step count per graph run (config-driven); exceeding it terminates the run with a `degraded` result rather than looping silently and burning tokens/cost. |
| AGENT-3.5 | Conflicting regulatory guidance | If `cross_reference_frameworks` (`AGENT-1.4`) detects two applicable rules that conflict rather than merely differ in strictness, the agent surfaces both with the conflict flagged explicitly, rather than silently picking one — this is a case for human judgment, and the system must say so. |

## AGENT-4 — Interfaces to FR-1..FR-4

| Functional requirement | Agent involvement |
|---|---|
| `FR-1` Q&A | Simple path may bypass the full agent graph and call `search_regulations` + generation directly when no cross-referencing/risk-scoring is needed (cost/latency optimization) — agent graph is reserved for genuinely multi-step reasoning. |
| `FR-2` Transaction screening | Full `AGENT-1.7` graph, this is the primary use case the agent is designed for. |
| `FR-3` Regulatory change impact | A separate, simpler graph reusing `search_regulations` + a diff-against-registry tool; triggered by ingestion (`RAG-1.5`), not by a user query. |
| `FR-4` Report generation | Orchestrates N `FR-2` assessments (already computed/cached) plus deterministic aggregation; does not re-run full agentic reasoning per transaction at report time. |
