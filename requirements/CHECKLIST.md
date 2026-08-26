# Master Checklist — FinServ Global AI Regulatory Compliance Assistant

Tracks completion against the assignment's 100-point rubric and its own submission checklist.
Update this file's status column as work progresses — it is the single place to check "what's
left."

**Legend:** ☐ Not started · 🔶 In progress · ✅ Done

---

## Phase 0 — Requirements & Architecture Definition (current phase)

| Item | Status | Artifact |
|---|---|---|
| Assignment brief restated as source of truth | ✅ | `00-assignment-brief.md` |
| Business context & personas documented | ✅ | `01-business-context-and-personas.md` |
| Functional requirements (FR-1..FR-5) | ✅ | `02-functional-requirements.md` |
| RAG pipeline requirements (RAG-1..RAG-7) | ✅ | `03-rag-pipeline-requirements.md` |
| LLM orchestration requirements (LLM-1..LLM-4) | ✅ | `04-llm-orchestration-requirements.md` |
| Agentic workflow requirements (AGENT-1..AGENT-4) | ✅ | `05-agentic-workflow-requirements.md` |
| Infrastructure & NFR requirements (INFRA-1..INFRA-5) | ✅ | `06-infrastructure-nfr-requirements.md` |
| Security & compliance requirements (SEC-1..SEC-4) | ✅ | `07-security-compliance-requirements.md` |
| Observability requirements (OBS-1..OBS-3) | ✅ | `08-observability-requirements.md` |
| Evaluation framework requirements (EVAL-1..EVAL-3) | ✅ | `09-evaluation-framework-requirements.md` |
| Consolidated technology stack | ✅ | `10-technology-stack.md` |
| Non-goals & assumptions | ✅ | `11-non-goals-and-assumptions.md` |
| 3 ADRs | ✅ | `adr/ADR-001..003` |
| Solution + tech stack PPT | ✅ | `docs/FinServ-AI-Compliance-Assistant-Solution.pptx` |
| **Plan / tech stack / feature list confirmed with stakeholder** | ☐ | — blocks Phase 1 |

---

## Rubric traceability — Part 1: Solution Architecture & Design (50 pts)

### 1A. End-to-End Architecture Document (25 pts)

| Sub-item | Status | Covered by |
|---|---|---|
| High-level architecture diagram | ✅ | `docs/` PPT, slide 6 |
| RAG pipeline design — ingestion (multi-format, versioned) | ✅ | `RAG-1` |
| RAG pipeline design — chunking strategy + justification | ✅ | `RAG-2` |
| RAG pipeline design — embedding model & vector DB + trade-off analysis | ✅ | `RAG-3`, `ADR-001` |
| RAG pipeline design — retrieval strategy (hybrid, re-rank, compression) | ✅ | `RAG-4` |
| RAG pipeline design — document updates/version control in vector store | ✅ | `RAG-5` |
| LLM orchestration — foundation model selection + rationale | ✅ | `LLM-1`, `ADR-002` |
| LLM orchestration — multi-model routing strategy | ✅ | `LLM-2` |
| LLM orchestration — prompt engineering framework | ✅ | `LLM-3` |
| LLM orchestration — guardrails | ✅ | `LLM-4` |
| Agentic workflow — agent design (KB query, cross-reference, transaction data, assessment) | ✅ | `AGENT-1` |
| Agentic workflow — tool definitions, state management, error handling | ✅ | `AGENT-1`, `AGENT-2`, `AGENT-3` |
| Agentic workflow — framework choice + why | ✅ | `AGENT-1.1`, `ADR-003` |

### 1B. Infrastructure & Non-Functional Requirements (15 pts)

| Sub-item | Status | Covered by |
|---|---|---|
| Cloud architecture — deployment topology + Kubernetes | ✅ | `INFRA-1` |
| Cloud architecture — auto-scaling for inference endpoints | ✅ | `INFRA-2` |
| Cloud architecture — cost estimate (500 concurrent users, 10K queries/day) | ✅ | `INFRA-3` |
| Security — data residency & encryption | ✅ | `SEC-1` |
| Security — model access controls & audit logging | ✅ | `SEC-2` |
| Security — no regulated data leak to external LLM providers | ✅ | `SEC-3` |
| Observability — LLM performance monitoring stack | ✅ | `OBS-1` |
| Observability — evaluation pipeline | ✅ | `OBS-2` |
| Observability — drift detection for retrieval relevance | ✅ | `OBS-3` |

### 1C. Architecture Decision Records (10 pts)

| ADR | Status | Artifact |
|---|---|---|
| Vector database selection | ✅ | `adr/ADR-001-vector-database-selection.md` |
| Model hosting strategy (self-hosted vs. API) | ✅ | `adr/ADR-002-model-hosting-strategy.md` |
| Build vs. buy for orchestration layer | ✅ | `adr/ADR-003-orchestration-layer-build-vs-buy.md` |

---

## Rubric traceability — Part 2: Hands-On Implementation (50 pts)

**Not started — explicitly deferred until the plan above is confirmed.** Requirements for this
phase are already specified (so development can start immediately once greenlit); nothing here
is blocked on further design work, only on go-ahead.

### 2A. RAG Pipeline (20 pts)

| Sub-item | Status | Spec |
|---|---|---|
| Ingest ≥5 sample regulatory documents | ☐ | `RAG-1.6` |
| Vector store setup (Qdrant) | ☐ | `RAG-3.2` |
| Hybrid search (semantic + keyword) | ☐ | `RAG-4.1` |
| Re-ranking step | ☐ | `RAG-4.3` |
| Cited, source-attributed answers | ☐ | `RAG-6` |
| Error handling | ☐ | `RAG-7` |

### 2B. Agentic Compliance Checker (20 pts)

| Sub-item | Status | Spec |
|---|---|---|
| Agent accepts transaction description | ☐ | `AGENT-1`, `FR-2` |
| Queries RAG pipeline for relevant regulations | ☐ | `AGENT-1.2` |
| Structured compliance assessment (risk rating, regulations, actions, citations) | ☐ | `FR-2.3`–`FR-2.5` |
| Handles ambiguous/insufficient information gracefully | ☐ | `AGENT-3.2` |
| Test against 4 sample transaction scenarios | ☐ | `00-assignment-brief.md` sample payloads |

### 2C. Evaluation Framework (10 pts)

| Sub-item | Status | Spec |
|---|---|---|
| 15–20 QA test dataset with ground truth | ☐ | `EVAL-1` |
| Faithfulness, answer relevance, context precision, context recall (RAGAS) | ☐ | `EVAL-2.1`–`EVAL-2.4` |
| Summary report with scores and failure analysis | ☐ | `EVAL-3` |

---

## Assignment's own submission checklist

| Item | Status |
|---|---|
| Architecture document with diagrams (PDF/Markdown) | ✅ — Markdown complete (`requirements/`), PPT with diagrams complete (`docs/`) |
| 3 Architecture Decision Records | ✅ |
| Code repository with README, setup instructions, sample outputs | ☐ — deferred to development phase |
| Evaluation report with RAGAS/custom metric scores | ☐ — spec done (`09-evaluation-framework-requirements.md`), report generated once code exists |

---

## Next gate

Development (Part 2) starts only after: (1) this checklist's Phase 0 rows are all ✅, and
(2) the plan, technology stack (`10-technology-stack.md`), and feature list (`02-functional-requirements.md`)
are explicitly confirmed.
