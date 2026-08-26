# Business Context & Personas

## Why this system exists

FinServ Global's compliance function is a manual, document-search-heavy operation that does not
scale with regulatory volume. The AI Regulatory Compliance Assistant exists to compress the
"find the rule → interpret it → apply it to this transaction → document why" loop from hours to
minutes, **without weakening the audit trail that loop currently produces on paper.**

## Pain points → capabilities (traceability)

| Pain point | Capability that addresses it | Requirement IDs |
|---|---|---|
| Manually searching regulatory PDFs (60%+ of officer time) | Cited natural-language Q&A over an indexed, versioned corpus | `FR-1`, `RAG-*` |
| Cross-referencing circulars by hand | Hybrid retrieval + cross-framework agent reasoning | `RAG-4`, `AGENT-1` |
| A single transaction can trigger multiple frameworks at once | Agentic transaction screening that queries all applicable frameworks | `FR-2`, `AGENT-1` |
| 200+ new circulars/amendments per year | Automated ingestion pipeline + regulatory-change-impact analysis | `RAG-1`, `FR-3` |
| Audit pressure — decisions must be traceable | Full decision lineage: query → retrieved chunks → prompt/model version → answer, immutable log | `SEC-2`, `AGENT-2` |
| Multi-jurisdiction (India/EU/US) | Region-pinned data residency, jurisdiction-aware retrieval filters | `SEC-1`, `RAG-3` |

## Personas and how the system serves each

### Compliance Officer — day-to-day checks
- **Primary interaction:** `FR-1` (Q&A) and `FR-2` (transaction screening).
- **Success criterion:** an answer with citations in well under the latency SLA (see
  `06-infrastructure-nfr-requirements.md`), phrased so it can be pasted directly into a case
  file without further verification of the source.
- **Failure mode to avoid:** a confident-sounding but uncited or hallucinated answer. Guardrails
  (`LLM-4`) exist primarily for this persona.

### Compliance Head — oversight & reporting
- **Primary interaction:** `FR-4` (report generation) and trend analysis over `FR-3` outputs.
- **Success criterion:** a structured, submission-ready report for a period/transaction set,
  generated on demand rather than compiled by hand.
- **Failure mode to avoid:** reports whose figures/citations can't be traced back to individual
  transaction assessments.

### Internal Auditor — post-facto review
- **Primary interaction:** does not query the assistant directly in the common case; consumes
  the **audit trail** the other two personas' usage produces.
- **Success criterion:** for any historical AI-assisted decision, can reconstruct: the original
  query/transaction, the regulations retrieved (with document version), the model(s) and prompt
  version used, the generated assessment, and any human override.
- **Failure mode to avoid:** any gap in the chain — this is the persona that turns "the model
  hallucinated" from an accuracy bug into a regulatory incident if it isn't caught and logged.

## Regulatory frameworks in scope for the prototype corpus

- **Basel III** (capital adequacy, large exposures) — global/India via RBI adoption.
- **MiFID II** — EU, retail investor protection / appropriateness assessments.
- **RBI master directions/circulars** — India, KYC, NBFC lending, priority sector reporting.

At least 5 sample documents spanning these three frameworks will be used to build and evaluate
the prototype (see `RAG-1`, `EVAL-1`).

## Market/jurisdiction implications for architecture

FinServ operates in **India, EU, and US** simultaneously. This directly drives two
non-negotiable architectural constraints carried through every other doc:

1. **Data residency:** regulated document text and transaction data must not leave the
   jurisdiction it originates from without an explicit, logged justification. See `SEC-1`.
2. **No silent external data leakage:** no regulated data is sent to a third-party/SaaS LLM API.
   Self-hosted, open-source models are the default inference path. See `SEC-3`, `ADR-002`.
