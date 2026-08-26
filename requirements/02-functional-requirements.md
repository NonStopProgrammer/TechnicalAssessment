# Functional Requirements

Four core scenarios, each broken into micro-requirements with acceptance criteria. IDs here are
referenced by RAG/LLM/Agent/Eval docs and will become the acceptance tests when development
starts.

---

## FR-1 — Natural-language regulatory Q&A

**Story:** As a Compliance Officer, I ask a natural-language question about a regulation and get
a cited, version-aware answer.

**Example:** "What are the capital adequacy requirements for Tier 1 under Basel III as amended
in 2023?"

| ID | Requirement | Acceptance criteria |
|---|---|---|
| FR-1.1 | Accept free-text queries via API | Returns 400 with a clear message on empty/oversized (>2k char) input |
| FR-1.2 | Retrieve relevant chunks via hybrid search + re-rank | Top-k context passed to LLM is the re-ranked set, not raw retrieval (see `RAG-4`) |
| FR-1.3 | Answer must cite source document, section/clause, and version/effective-date | Every factual sentence in the answer maps to at least one retrieved chunk id; citations rendered as `[DocID §Clause, v:YYYY-MM-DD]` |
| FR-1.4 | Answer must be version-aware | If a queried topic has a superseded and a current version, the current one is used by default; user can request "as of [date]" to get a historical answer |
| FR-1.5 | Graceful no-answer | If no chunk clears the relevance threshold, respond "insufficient information in the indexed corpus" rather than generating from parametric knowledge |
| FR-1.6 | Latency | P95 end-to-end (query → answer) ≤ 6s for cached/warm retrieval path (see NFR latency budget in `06-infrastructure-nfr-requirements.md`) |

---

## FR-2 — Transaction screening

**Story:** As a Compliance Officer, I submit a transaction payload and get a risk-rated
compliance assessment against all applicable frameworks.

**Input payload (minimum fields):** `amount`, `currency`, `counterparty`, `counterparty_kyc_status`,
`jurisdiction(s)`, `instrument_type`, `customer_type` (retail/institutional/intra-group),
`transaction_type` (e.g., cross-border payment, derivative trade, lending, investment).

| ID | Requirement | Acceptance criteria |
|---|---|---|
| FR-2.1 | Validate payload schema | Missing required field → structured error naming the field, not a generic 500 |
| FR-2.2 | Identify all applicable frameworks | For a payload spanning jurisdictions (e.g., cross-border), all relevant frameworks are checked, not just one (this is the "cross-regulation complexity" pain point) |
| FR-2.3 | Produce a risk rating | One of `LOW / MEDIUM / HIGH / CRITICAL`, with the rule(s)/threshold(s) that drove the rating stated explicitly |
| FR-2.4 | List required actions | E.g., "escalate for enhanced due diligence", "block pending KYC", "file priority sector report" |
| FR-2.5 | Cite the regulation(s) backing each flag | Same citation format as `FR-1.3` |
| FR-2.6 | Handle ambiguous/incomplete payloads | If a required fact is missing (e.g., KYC status unknown), the assessment states the assumption made or asks a clarifying question — never silently assumes "compliant" |

**Reference test cases (from assignment, also seed `EVAL-1`):**

1. Cross-border payment of $2M to a non-KYC-verified entity in a high-risk jurisdiction →
   expect `CRITICAL`/`HIGH`, KYC + high-risk-jurisdiction rules cited.
2. Intra-group derivative trade exceeding large exposure threshold → expect Basel III large
   exposure framework cited.
3. Retail customer investment in a complex product without appropriateness assessment → expect
   MiFID II appropriateness-assessment rule cited.
4. NBFC lending transaction requiring priority sector reporting → expect RBI priority-sector
   directive cited.

---

## FR-3 — Regulatory change impact analysis

**Story:** As a Compliance Head, when a new circular is ingested, I want to know which existing
policies/transaction types it affects, so nothing falls through the cracks between review
cycles.

| ID | Requirement | Acceptance criteria |
|---|---|---|
| FR-3.1 | Trigger on new document ingestion | Ingesting a document tagged as an amendment/circular update automatically runs an impact scan (not manually invoked) |
| FR-3.2 | Diff against superseded content | Identify which clauses changed vs. the prior version of the same regulation (see `RAG-5` versioning) |
| FR-3.3 | Map changed clauses to affected transaction types/policies | Output a list of transaction types (from `FR-2`'s taxonomy) whose screening rules may need review |
| FR-3.4 | Human-in-the-loop | Output is a review queue item for a Compliance Head, not an auto-applied policy change |

---

## FR-4 — Compliance report generation

**Story:** As a Compliance Head, I generate a structured report for a set of transactions over a
period, ready for the internal audit committee.

| ID | Requirement | Acceptance criteria |
|---|---|---|
| FR-4.1 | Accept a filter (date range, transaction type, jurisdiction, risk rating) | Report scope matches filter exactly |
| FR-4.2 | Structured output | Sections: executive summary, methodology, per-transaction assessments (from `FR-2` outputs), aggregate risk trend, citations appendix |
| FR-4.3 | Deterministic aggregation, generative narrative | Counts/statistics are computed, not LLM-generated; only narrative summary text is LLM-generated, and is checked against the computed numbers by a guardrail (`LLM-4`) |
| FR-4.4 | Exportable | Markdown + PDF output |
| FR-4.5 | Every transaction's assessment in the report links back to its full audit trail entry | Supports Internal Auditor persona directly |

---

## Cross-cutting functional requirement

| ID | Requirement |
|---|---|
| FR-5 | Every response from FR-1–FR-4 carries a machine-readable provenance block (model id + version, prompt template id + version, retrieved chunk ids, timestamp) in addition to the human-readable answer — this is what makes `SEC-2` (audit logging) possible without re-deriving lineage after the fact. |
