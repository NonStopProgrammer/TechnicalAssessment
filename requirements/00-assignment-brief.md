# Assignment Brief (Source of Truth)

Restated from `AI_Architect_Assignment.pdf`. This file is the canonical reference every other
requirements doc traces back to — if a later doc and this one ever disagree, this one wins.

## Engagement

- **Role:** AI Architect for **FinServ Global** — a mid-large financial services company
  operating across **India, EU, and US** markets.
- **Deliverable:** An AI-powered **Regulatory Compliance Assistant**.
- **Duration:** 5 days. **Submission:** Architecture doc (PDF/Markdown) + diagrams + code repo.
- **Hard constraint:** Open-source data, models, and libraries only. Any proprietary/paid
  service referenced must be called out with an open-source alternative used in the prototype.

## Business context

- ~40 compliance officers spend 60%+ of their time manually searching PDFs, cross-referencing
  circulars, preparing audit-ready reports.
- 200+ new circulars/amendments per year (Basel III, MiFID II, RBI master directions).
- A single transaction can trigger obligations under multiple frameworks at once.
- Regulators require documented, traceable evidence of how compliance decisions were reached.

## What "good" looks like (grader's own words)

- **Production-aware**, not tutorial-grade: scale, failure modes, regulation churn, model
  deprecation, cost growth.
- **Working code that reflects the architecture** — a faithful slice, not a disconnected
  notebook. Modularity, config-driven behavior, separation of concerns.
- **Defensible trade-offs** for every major choice, grounded in FinServ's context (regulatory
  sensitivity, latency SLAs, data residency).

## What NOT to do

- Generic LangChain-tutorial-as-architecture.
- Single LLM provider with no fallback or cost controls.
- Ignoring data sovereignty (e.g., RBI circular text sent to US-hosted APIs unaddressed).

## Rubric (100 points total)

| Part | Section | Points | Requirements doc(s) covering it |
|---|---|---|---|
| 1A | High-level architecture diagram | (in 25) | `10-technology-stack.md`, PPT |
| 1A | RAG pipeline design | (in 25) | `03-rag-pipeline-requirements.md` |
| 1A | LLM orchestration layer | (in 25) | `04-llm-orchestration-requirements.md` |
| 1A | Agentic workflow design | (in 25) | `05-agentic-workflow-requirements.md` |
| 1B | Cloud architecture (AWS/Azure/GCP) | (in 15) | `06-infrastructure-nfr-requirements.md` |
| 1B | Security & compliance | (in 15) | `07-security-compliance-requirements.md` |
| 1B | Observability | (in 15) | `08-observability-requirements.md` |
| 1C | 3 ADRs | 10 | `adr/ADR-001..003` |
| 2A | RAG pipeline (code) | 20 | deferred to development phase |
| 2B | Agentic compliance checker (code) | 20 | deferred to development phase |
| 2C | Evaluation framework (code) | 10 | `09-evaluation-framework-requirements.md` (spec now, code later) |

## Core scenarios the system must handle (→ Functional Requirements)

1. Natural-language regulatory Q&A → cited, versioned answer (`FR-1`)
2. Transaction screening → risk-rated compliance assessment (`FR-2`)
3. Regulatory change impact analysis → affected policies/transaction types (`FR-3`)
4. Structured compliance report generation for a period → audit-committee ready (`FR-4`)

## Sample transaction payloads (drive `FR-2` acceptance criteria and 2B test cases)

1. Cross-border payment of $2M to a non-KYC-verified entity in a high-risk jurisdiction.
2. Intra-group derivative trade exceeding the large exposure threshold.
3. Retail customer investment in a complex product without an appropriateness assessment
   (MiFID II).
4. NBFC lending transaction requiring priority sector reporting (RBI).

## Target personas (→ `01-business-context-and-personas.md`)

| Persona | Role | Primary need |
|---|---|---|
| Compliance Officer | Day-to-day checks | Fast, cited answers: "Does this transaction violate any regulation?" |
| Compliance Head | Oversight & reporting | Weekly/monthly compliance posture reports, trend analysis |
| Internal Auditor | Post-facto review | Audit trail of every AI-assisted decision, with source citations |

## Submission checklist (assignment's own, mirrored in `CHECKLIST.md`)

- [ ] Architecture document with diagrams (PDF/Markdown)
- [ ] 3 Architecture Decision Records
- [ ] Code repository with README, setup instructions, sample outputs
- [ ] Evaluation report with RAGAS/custom metric scores
