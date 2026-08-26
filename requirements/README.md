# Requirements — FinServ Global AI Regulatory Compliance Assistant

This folder is the working requirements backlog for the "AI Architect – Technical Assignment"
(FinServ Global Regulatory Compliance Assistant). It decomposes the assignment brief into
micro-level, traceable requirements that map directly to the evaluation rubric, so nothing in
the 100-point scoring is missed and every design decision can be defended.

**Status of this phase:** Architecture & requirements definition only. No application code is
written yet — see `CHECKLIST.md` for what's done vs. pending, and `docs/` for the companion
solution presentation. Development starts only after the plan, tech stack, and feature list
below are confirmed.

## Reading order

| # | File | Covers |
|---|------|--------|
| 00 | `00-assignment-brief.md` | Source-of-truth restatement of the assignment + rubric |
| 01 | `01-business-context-and-personas.md` | Why this system exists, who uses it |
| 02 | `02-functional-requirements.md` | The 4 core scenarios (FR-1..FR-4) |
| 03 | `03-rag-pipeline-requirements.md` | Ingestion, chunking, embeddings, vector DB, retrieval |
| 04 | `04-llm-orchestration-requirements.md` | Model selection, routing, prompting, guardrails |
| 05 | `05-agentic-workflow-requirements.md` | Compliance agent, tools, state, error handling |
| 06 | `06-infrastructure-nfr-requirements.md` | Cloud, Kubernetes, autoscaling, cost |
| 07 | `07-security-compliance-requirements.md` | Data residency, encryption, access, audit |
| 08 | `08-observability-requirements.md` | Monitoring, eval pipeline, drift detection |
| 09 | `09-evaluation-framework-requirements.md` | RAGAS test set, metrics, report |
| 10 | `10-technology-stack.md` | Consolidated stack decisions + OSS-alternative call-outs |
| 11 | `11-non-goals-and-assumptions.md` | Explicit scope boundaries and assumptions |
| — | `adr/ADR-00x-*.md` | 3 Architecture Decision Records |
| — | `CHECKLIST.md` | Master tracking checklist, mapped to the rubric |

## Conventions

- Every requirement has a stable ID (`FR-1`, `RAG-3`, `AGENT-2`, …) used consistently across
  requirements docs, ADRs, the PPT, and (later) code/tests for traceability.
- "Open-source only" is a hard constraint from the assignment. Any place a proprietary/paid
  service is mentioned, it is explicitly flagged **[PROPRIETARY]** with an **[OSS ALTERNATIVE]**
  that the prototype will actually use.
- Requirements are written at "micro" granularity — small enough to become a single backlog
  ticket/PR when development starts.
