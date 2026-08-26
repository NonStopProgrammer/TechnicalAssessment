# FinServ Global — AI Regulatory Compliance Assistant

## Executive Summary

A production-ready MVP of an AI-powered regulatory compliance assistant for mid-to-large financial services operating across India, EU, and US markets. The system performs intelligent transaction screening, regulatory question-answering, and cross-framework compliance assessment against Basel III, MiFID II, and RBI regulations using a modern RAG + agentic workflow architecture.

**Status:** MVP complete with full test coverage (66 passing tests), end-to-end validation, and evaluation metrics (19/20 QA pairs passing, 0.975 citation accuracy, 4/4 risk-rating accuracy).

---

## The Challenge — What This Solves

### Challenge Problem 1: Multi-Framework Regulatory Compliance

**Problem:** Financial institutions operating across multiple jurisdictions (India, EU, US) must comply with different, sometimes overlapping regulatory frameworks (Basel III, MiFID II, RBI KYC/PSL). Manually cross-referencing regulations and assessing transaction compliance is error-prone and slow.

**Solution:** 
- **RAG Pipeline** (`code/rag/`) ingests 6+ regulatory documents (Basel III capital adequacy & large exposure rules, MiFID II investor protection, RBI KYC master direction & priority sector lending)
- **Hybrid retrieval** (dense semantic + sparse lexical) via RRF fusion returns regulation clauses most relevant to a query, with re-ranking to surface top-8 candidates
- **Stored in:** SQLite registry + Qdrant vector store (regional collections for IN/EU/US + global regulations replicated into each region)
- **Result:** Compliance officers can query "What are the Tier 1 capital requirements?" and get Basel III §6.2 cited with version/jurisdiction info in <1s

### Challenge Problem 2: Transaction Risk Assessment

**Problem:** Daily transaction flows (wire transfers, derivatives, investments, lending) must be screened for compliance violations. A single transaction often triggers multiple regulatory rules across different frameworks.

**Solution:**
- **Agentic Workflow** (`code/agentic/graph/`) — LangGraph state machine with 8 deterministic steps:
  1. **Classify** transaction type & applicable frameworks
  2. **Retrieve** relevant regulations from RAG
  3. **Cross-reference** frameworks to detect conflicts
  4. **Score risk** via deterministic rule logic (never LLM-guessed), per scenario:
     - Cross-border payment to unverified KYC → RBI threshold check → escalate to MLRO if >$1M
     - Large intra-group derivative exposure → Basel III 25% Tier 1 limit check
     - Retail structured note sale → MiFID II appropriateness assessment requirement
     - NBFC lending → RBI priority sector lending classification
  5. **Generate citations** linking each rule to the retrieved regulation clause
  6. **Draft narrative** via LLM (but LLM only narrates; risk rating is deterministic)
  7. **Verify citations** — validate that every cited clause was actually retrieved
  8. **Finalize assessment** with structured output: risk_rating, rule_triggers, required_actions, citations

- **Stored in:** LangGraph checkpoint state (audit trail), SQLite `assessment_records` table (for reporting)
- **Result:** Transaction `{amount: 2M, counterparty: "Meridian Offshore", counterparty_kyc_status: "not_verified", jurisdiction: "IN"}` → `risk_rating: CRITICAL`, `required_actions: ["Block transaction, escalate to MLRO"]`, `citations: [RBI-KYC-MASTER-DIRECTION §3.3]`

### Challenge Problem 3: Regulatory Change Impact Assessment

**Problem:** When a regulation is amended (e.g., Basel III 2023 adds the Countercyclical Capital Buffer), the organization must know which transaction types and policies are affected, and update procedures accordingly.

**Solution:**
- **Impact Workflow** (`code/agentic/impact/build_impact_graph.py`) triggered on document ingestion:
  - Diff old vs. new regulation versions clause-by-clause
  - Extract which transaction types are affected (via framework mappings)
  - Generate human-readable impact summary via LLM
  - Queue item in `impact_review_items` table (FR-3.4) for Compliance Head review — **never auto-applies**, always human-in-the-loop
- **Result:** Basel III 2023 amendment ingested → pending review item created → Compliance Head reviews and marks as resolved

### Challenge Problem 4: Audit & Compliance Reporting

**Problem:** Regulators and internal auditors need to reconstruct every AI-assisted compliance decision: which regulations were retrieved, which model versions were used, what confidence score was assigned, and what data was considered.

**Solution:**
- **Audit Trail** (SEC-2.3): Every FR-1..FR-4 request logged to `audit_log_entries` table with:
  - User ID, role, timestamp, endpoint
  - PII-redacted input/output
  - Retrieved chunk IDs, model/prompt version, confidence score
  - All queryable by internal auditors via read-only `/api/v1/audit-log` endpoint
- **Report Generation** (FR-4): Aggregates already-computed assessments (not re-running the agent graph) and produces markdown + PDF with:
  - Transaction counts by risk rating, framework, jurisdiction
  - Per-transaction breakdown linking to audit trail
  - LLM-only narrates statistics (LLM-4.6 guardrail: numeric consistency checked)
- **Stored in:** `report_records` table + `/var/reports/*.md` files
- **Result:** Auditor queries `/api/v1/audit-log?user_id=officer@finserv.demo` → full decision lineage; generates compliance report for a quarter → PDF ready for regulator

### Challenge Problem 5: Cross-Geographic Data Residency

**Problem:** Indian regulations require customer data to stay in-country; EU has GDPR; US has Gramm-Leach-Bliley. A centralized vector store violates this.

**Solution:**
- **Multi-Region Architecture** (`code/rag/vectorstore/`):
  - Separate Qdrant collections per region (IN, EU, US) — each region's data never leaves that region's database
  - Global regulations (Basel III, MiFID II rules) replicated into **every** region's collection so all regions can enforce them, but tagged with `jurisdiction: GLOBAL` so audit trail is clear
  - Query filter includes both regional data (`jurisdiction: IN`) **and** GLOBAL regulations
- **Stored in:** `regulations_in`, `regulations_eu`, `regulations_us` Qdrant collections (one per region)
- **Result:** Transaction in India queried against `regulations_in` (which contains regional RBI rules + replicated Basel III/MiFID II rules) — no cross-region networking, data stays in-country

---

## Architecture Overview

### High-Level Flow

```
Transaction / Query Input
    ↓
[RAG Pipeline] ← Ingest & index regulations
    ↓ (retrieve relevant clauses)
[Agentic Compliance Checker] ← LangGraph state machine
    ↓ (classify, retrieve, cross-ref, score, draft, verify)
[Structured Compliance Assessment] ← Risk rating + citations + provenance
    ↓
[Backend API] ← FastAPI REST endpoints (FR-1..FR-4)
    ↓
[Frontend / MCP Server] ← React UI + Model Context Protocol tools
    ↓
[Audit Trail & Reports] ← Persistent assessment + decision lineage
```

### System Components

#### 1. **RAG Pipeline** (`code/rag/`)
Retrieval-Augmented Generation layer for embedding regulations and answering compliance queries.

**Components:**
- **Ingestion** (`rag/ingestion/`):
  - Multi-format parsing: Markdown, HTML, PDF, DOCX
  - Metadata extraction: framework, jurisdiction, effective_date, version
  - Idempotent deduplication via checksum (same bytes = already indexed)
  - Version control: amendments append new rows, mark old versions `superseded_by`

- **Chunking** (`rag/chunking/`):
  - Clause-bounded splitting (detects `### 6.1 Title` pattern)
  - Recursive fallback for long clauses (~512 tokens max per chunk)
  - ~15% overlap at boundaries to preserve context

- **Embeddings** (`rag/embeddings/`):
  - MVP: `local_hash` (bag-of-words, deterministic, zero dependencies)
  - Production: TEI adapter for BAAI/bge-large-en-v1.5 semantic embeddings
  - Both implement same interface; swapped via `EMBEDDING_PROVIDER=` env var

- **Vector Store** (`rag/vectorstore/`):
  - Qdrant (embedded SQLite by default, server mode optional)
  - Multi-region collections (regulations_in, regulations_eu, regulations_us)
  - Payload indexes on framework, jurisdiction, effective_date, version for filtering

- **Retrieval** (`rag/retrieval/`):
  - Hybrid search: dense (semantic) + sparse (lexical) via RRF fusion
  - Re-ranking: lexical overlap (MVP) or cross-encoder (production)
  - Contextual compression: passthrough (MVP) or LLMLingua (production)
  - Relevance floor (0.16) filters low-confidence results

**Stored Regulations** (`code/rag/corpus/sample_documents/`):
- `basel_iii_capital_adequacy_2019.md` — CET1 4.5%, Tier1 6.0%, Total 8.0%
- `basel_iii_capital_adequacy_2023.md` — adds Countercyclical Buffer 0-2.5%
- `basel_iii_large_exposures.md` — 25% Tier 1 limit, 15% for G-SIBs, intra-group same rules
- `mifid_ii_appropriateness.md` — retail clients, complex products, appropriateness assessment required
- `rbi_kyc_master_direction.md` — KYC required, >$1M non-KYC + high-risk → MLRO escalation
- `rbi_priority_sector_lending.md` — 40% PSL target, quarterly reporting, shortfall deposits

#### 2. **LLM Orchestration** (`code/llm/`)
Multi-provider routing, prompt management, and guardrails for language model inference.

**Components:**
- **Provider Abstraction** (`llm/providers/`):
  - MVP: `local_stub` (purely extractive; parses `[CONTEXT #n]` blocks from prompts, never hallucinates)
  - Production: vLLM adapter for Llama-3.1-8B (router) / 70B (generation)
  - Both implement `generate(system_prompt, user_prompt, response_schema)` interface

- **Routing & Fallback** (`llm/router.py`):
  - Task→tier mapping (intent classification, pii prescan → 8B router; text generation → 70B)
  - Fallback chain: primary (self-hosted) → secondary (local_stub) — **never falls back to external SaaS** for regulated data
  - Circuit breaker: after 3 consecutive failures, open circuit for 60s

- **Prompt Templates** (`llm/prompts/`):
  - Versioned Jinja2 templates (qa_answer.v1.jinja2, transaction_screening.v1.jinja2, etc.)
  - System prompt specifies role, citation format, refusal conditions
  - Few-shot examples for edge cases (refusal, unrelated context)

- **Guardrails** (`llm/guardrails/`):
  - PII redaction: regex patterns for email, phone, PAN, Aadhaar, card numbers
  - Citation verification: confirm LLM-cited chunks were actually retrieved
  - Topical rail: keyword-based scope check (compliance-related vs. off-topic)
  - Numeric consistency: for reports, verify LLM-generated numbers match computed stats

**Where Used:**
- FR-1: Q&A endpoint calls `generate_structured(task="qa_answer", ...)`
- FR-2: Transaction screening agent's `draft_assessment` node calls LLM to narrate a pre-computed risk rating
- FR-4: Report generation LLM narrates statistics (never invents them)

#### 3. **Agentic Workflow** (`code/agentic/`)
LangGraph state machine orchestrating the multi-step compliance assessment.

**Graph Structure** (`agentic/graph/build_graph.py`):
```
classify_input → retrieve → cross_reference → score_risk → draft_assessment → verify_citations → finalize
                                                                ↑                    ↓
                                                          (if citation fail        (retry draft)
                                                           & retries left)
                                                                    ↓
                                                            degraded (fallback)
```

**State** (`agentic/state.py`):
- Full decision lineage persisted at every node transition (checkpoint = audit trail)
- Tracks: input transaction, applicable frameworks, retrieved chunks, risk score, citations, LLM outputs, verification results

**Tools** (`agentic/tools/`):
- `search_regulations`: RAG retrieval
- `get_transaction_details`: fetch from seeded store (TXN-1001..1005)
- `calculate_risk_rating`: deterministic rule scoring
- `cross_reference_frameworks`: extract thresholds, detect conflicts
- `generate_citation_bundle`: match findings to retrieved clauses

**Nodes**:
- `classify_input`: determine applicable frameworks
- `retrieve`: call RAG for relevant regulations
- `cross_reference`: resolve overlapping/conflicting rules
- `score_risk`: apply deterministic scoring logic
- `draft_assessment`: LLM narrates the risk rating (doesn't invent it)
- `verify_citations`: validate all citations were retrieved
- `finalize`: build structured output + provenance
- `degraded`: fallback node for unrecoverable errors

**Stored:**
- Checkpoint history in PostgreSQL (production) or memory (MVP)
- Seeded transactions in `agentic/seed_data/transactions.json`
- Assessment records in `assessment_records` table

#### 4. **Backend API** (`code/backend/`)
FastAPI application exposing compliance functions over HTTP REST.

**Endpoints:**
- **FR-1: Q&A** `POST /api/v1/qa` — answer regulatory questions with citations
- **FR-2: Transaction Screening** `POST /api/v1/screening` — assess transaction compliance
- **FR-4: Report Generation** `POST /api/v1/reports` — aggregate and report on assessments
- **FR-4: Download** `GET /api/v1/reports/{id}/markdown`, `/pdf` — export reports
- **FR-3.4: Impact Review** `GET /api/v1/impact-review-queue` — view pending regulatory change impacts
- **SEC-2.3: Audit Trail** `GET /api/v1/audit-log`, `/audit-log/{request_id}` — read-only for auditors
- **SEC-2.1: Auth** `POST /api/v1/auth/dev-token` — dev-only token issuance (swap with Keycloak OIDC in production)
- **Health** `GET /api/v1/health` — liveness check

**Security** (SEC-2):
- Role-based access control (RBAC): compliance_officer, compliance_head, internal_auditor, platform_admin
- PII redaction before logging (`input_redacted`, `output_redacted` in audit table)
- Rate limiting, input validation, error messages don't leak internals

**Stored:**
- Audit log: `audit_log_entries` table
- Assessments: `assessment_records` table
- Reports: `report_records` table + `/var/reports/*.md` files

#### 5. **MCP Server** (`code/mcp/fincompliance_mcp/`)
Model Context Protocol server exposing tools to Claude Desktop and other clients.

**Tools exposed:**
- `search_regulations` — RAG search
- `answer_compliance_question` — FR-1 Q&A
- `get_transaction_details` — fetch seeded transaction
- `screen_transaction` — full FR-2 screening
- `screen_seeded_transaction` — one-click demo

**Stored in:**
- `mcp/fincompliance_mcp/server.py` — tool definitions

#### 6. **Evaluation Framework** (`code/eval/`)
Automated evaluation against a 20-question ground-truth dataset.

**Metrics:**
- **Citation Accuracy** (floor 0.90): % of LLM-cited chunks that match expected citations
- **Risk-Rating Accuracy** (floor 4/4): all 4 reference scenarios produce expected severity
- **RAGAS Metrics** (floor 0.80-0.85): faithfulness, answer_relevance, context_precision, context_recall
  - Note: LLM-judged metrics (RAGAS) report as "skipped" under the MVP's `local_stub` LLM (no judge available)

**Results** (`code/eval/reports/`):
- `latest.md` — human-readable report with per-question breakdown
- `latest.json` — machine-readable scores

---

## Technology Stack

### Core Stack

| Layer | MVP Default | Production Adapter | Why |
|---|---|---|
| **Ingestion** | Python (pypdf, python-docx, beautifulsoup4) | Apache Airflow DAG | Lightweight local, cloud-scale with Airflow |
| **Vector Store** | Qdrant embedded (SQLite) | Qdrant server (EKS) | Zero-infra locally, distributed in cloud |
| **Embeddings** | `local_hash` (CRC32 hash bag-of-words) | BAAI/bge-large-en-v1.5 (HF TEI) | No GPU needed locally, production semantic search |
| **LLM** | `local_stub` (extractive template-filler) | Llama-3.1-70B (vLLM) | Deterministic, no hallucination locally; production generation |
| **Reranker** | Lexical overlap heuristic | BAAI/bge-reranker-large (TEI) | Fast heuristic locally, production cross-encoder ranking |
| **Database** | SQLite | PostgreSQL / RDS | Local file-based, cloud-managed in production |
| **Cache** | In-memory | Redis | Local, distributed cache in production |
| **API** | FastAPI | FastAPI (same, scaled) | Lightweight async server, same code at scale |
| **Agent** | LangGraph | LangGraph (same) | Deterministic graph, no vendor lock-in |
| **Frontend** | React + TypeScript + Vite | React + TypeScript (same) | Modern SPA, works locally and in cloud |

### Language & Frameworks

```
Python 3.11+
├── FastAPI (REST API)
├── SQLAlchemy (ORM)
├── LangGraph (agentic workflow)
├── Pydantic (data validation)
├── Qdrant (vector store client)
├── Structlog (structured logging)
├── pytest (testing)
└── (Optional in requirements-full.txt):
    ├── vLLM (LLM serving)
    ├── sentence-transformers (embeddings)
    ├── nemoguardrails (guardrails)
    ├── presidio-analyzer (PII detection)
    ├── ragas (evaluation metrics)
    └── apache-airflow (orchestration)

TypeScript + React
├── Vite (build tool)
├── React Router (navigation)
└── Axios (HTTP client)

Infrastructure (reference, not deployed)
├── Terraform (EKS + node pools)
└── Kubernetes (deployment manifests)
```

---

## How to Run the Project

### Quick Start (5 minutes)

**Prerequisites:** Python 3.11+, pip, npm

```bash
# 1. Clone and navigate
cd code

# 2. Set up Python environment
python -m venv .venv
source .venv/Scripts/activate     # Windows: .venv\Scripts\Activate.ps1

# 3. Install dependencies (zero GPU required)
pip install -r requirements.txt

# 4. Copy environment config (defaults work out-of-the-box)
cp .env.example .env

# 5. Seed regulations + demo transactions
python -m scripts.seed_corpus

# 6. Start the backend API
uvicorn backend.main:api --reload --port 8080
# → Visit http://localhost:8080/docs for OpenAPI UI
```

### Run the Frontend (in a second terminal)

```bash
cd code/frontend
npm install
npm run dev
# → Open http://localhost:5173 in browser
# → Sign in as "officer@finserv.demo" (role: compliance_officer)
# → Try Q&A, Screening, Reports
```

### Run Tests

```bash
cd code
pytest -v                          # All 66 tests
pytest backend/tests -v            # API tests only
pytest rag/tests -v                # RAG pipeline tests
cd frontend && npm run typecheck   # TypeScript type check
```

### Run Evaluation Framework

```bash
cd code
python -m eval.run_evaluation
# → Generates code/eval/reports/latest.md with scores
# → Expected: citation_accuracy ~0.97, risk_rating_accuracy 4/4
```

### Run MCP Server (for Claude Desktop)

```bash
cd code
PYTHONPATH=.:./mcp MCP_TRANSPORT=stdio python -m fincompliance_mcp.server
# Then wire into Claude Desktop's config (see code/mcp/README.md)
```

### Docker Compose (Full Stack)

```bash
cd code
docker compose up --build
# → Backend: http://localhost:8080/api/v1
# → Frontend: http://localhost:5173
# → MCP server: http://localhost:8090 (SSE)
# → Qdrant UI: http://localhost:6333/dashboard
# → Postgres: localhost:5432 (postgres/password)
```

### Try the API (via curl)

```bash
# 1. Get a demo token
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/dev-token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "officer@finserv.demo", "role": "compliance_officer"}' \
  | jq -r '.access_token')

# 2. Ask a regulatory question (FR-1)
curl -X POST http://localhost:8080/api/v1/qa \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the Tier 1 capital requirements?", "jurisdictions": ["IN"]}'

# 3. Screen a transaction (FR-2)
curl -X POST http://localhost:8080/api/v1/screening \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 2000000,
    "currency": "USD",
    "counterparty": "Meridian Offshore Holdings Ltd",
    "counterparty_kyc_status": "not_verified",
    "jurisdictions": ["IN"],
    "instrument_type": "wire_transfer",
    "customer_type": "institutional",
    "transaction_type": "cross_border_payment"
  }'
# → Expected: risk_rating: CRITICAL, cites RBI-KYC-MASTER-DIRECTION §3.3
```

---

## Project Structure & Solution Storage

```
code/
├── shared/                 # Domain models, config, logging, database
│   ├── config.py          # Env-driven settings (all provider flags here)
│   ├── enums.py           # Framework, Jurisdiction, RiskRating, etc.
│   ├── ids.py             # ID generation, citation formatting
│   ├── models/            # Pydantic schemas (Document, Chunk, Citation, Assessment, etc.)
│   └── db/                # SQLAlchemy ORM, database connection
│
├── rag/                   # Retrieval-Augmented Generation pipeline
│   ├── ingestion/         # Multi-format parsing, chunking, versioning
│   │   ├── parsers.py     # PDF, DOCX, HTML, Markdown parsing
│   │   ├── metadata_extraction.py
│   │   ├── registry.py    # DocumentRegistry table (idempotent dedup)
│   │   └── pipeline.py    # Ingest orchestrator
│   ├── embeddings/        # Embedding providers (local_hash, TEI adapter)
│   ├── vectorstore/       # Qdrant client (multi-region collections)
│   ├── retrieval/         # Hybrid search, re-ranking, compression
│   ├── corpus/sample_documents/  # 6 sample regulations
│   ├── tests/
│   └── README.md
│
├── llm/                   # Language model orchestration
│   ├── providers/         # local_stub (extractive), vLLM adapter
│   ├── router.py          # Multi-provider fallback + circuit breaker
│   ├── prompts/           # Versioned Jinja2 templates
│   ├── response_models.py # Pydantic output schemas
│   ├── guardrails/        # PII redaction, citation verification, topical rail, numeric consistency
│   ├── config/            # Routing rules, model registry
│   ├── tests/
│   └── README.md
│
├── agentic/               # Compliance assessment agent (LangGraph)
│   ├── state.py           # ComplianceGraphState (decision lineage)
│   ├── graph/
│   │   ├── nodes.py       # 8 nodes (classify→retrieve→cross_ref→score→draft→verify→finalize)
│   │   ├── build_graph.py # Graph wiring + run_screening() entrypoint
│   │   └── checkpointer.py # PostgreSQL checkpoint storage
│   ├── tools/             # search_regulations, score_risk, cross_reference, etc.
│   ├── impact/            # FR-3 regulatory change impact analysis
│   ├── seed_data/transactions.json  # 5 seeded demo transactions
│   ├── qa.py              # FR-1 fast path (no full agent graph)
│   ├── tests/
│   └── README.md
│
├── mcp/                   # Model Context Protocol server
│   ├── fincompliance_mcp/
│   │   ├── __init__.py
│   │   └── server.py      # MCP tool definitions
│   ├── tests/
│   ├── Dockerfile
│   └── README.md
│
├── backend/               # FastAPI REST API
│   ├── main.py            # App entry point + lifespan setup
│   ├── core/
│   │   ├── security.py    # Auth (JWT), RBAC
│   │   ├── audit.py       # Audit log writer
│   │   └── errors.py      # Exception handlers
│   ├── schemas/           # Request/response Pydantic models
│   ├── services/          # qa_service, screening_service, report_service, etc.
│   ├── api/v1/
│   │   ├── endpoints/     # qa, screening, reports, impact, audit, health
│   │   └── router.py      # Endpoint aggregator
│   ├── tests/
│   ├── Dockerfile
│   └── README.md
│
├── frontend/              # React + TypeScript demo UI
│   ├── src/
│   │   ├── pages/         # QA, Screening, Reports, Audit Trail pages
│   │   ├── components/    # RiskBadge, CitationList, Layout
│   │   ├── api/           # API client, types
│   │   ├── auth/          # Auth context (JWT)
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── README.md
│
├── eval/                  # Evaluation framework (RAGAS + custom metrics)
│   ├── datasets/qa_ground_truth.json     # 20 QA test pairs
│   ├── metrics/
│   │   ├── citation_accuracy.py          # Custom: % citations matching
│   │   ├── risk_rating_accuracy.py       # Custom: % scenarios at expected severity
│   │   └── ragas_runner.py               # RAGAS integration (faithfulness, etc.)
│   ├── run_evaluation.py                 # Evaluation orchestrator
│   ├── reports/latest.md, latest.json    # Output reports
│   ├── tests/
│   └── README.md
│
├── infra/                 # Reference architecture (Terraform + K8s)
│   ├── terraform/         # EKS clusters, node pools (not deployed)
│   ├── k8s/               # Namespace separation, network policies
│   └── README.md
│
├── scripts/
│   ├── seed_corpus.py     # One-shot: ingest regulations + seed transactions
│   └── smoke_test.py      # End-to-end API validation
│
├── requirements.txt       # MVP dependencies (no GPU needed)
├── requirements-full.txt  # Production heavy deps (GPU, LLMs, etc.)
├── docker-compose.yml     # Local dev topology (Postgres, Qdrant, Redis, etc.)
├── .env.example           # Config template
└── README.md              # This file
```

---

## Solving the Challenge: Detailed Walkthrough

### Scenario 1: Cross-Border Payment (High-Risk KYC Violation)

**Transaction Input:**
```json
{
  "amount": 2000000,
  "currency": "USD",
  "counterparty": "Meridian Offshore Holdings Ltd",
  "counterparty_kyc_status": "not_verified",
  "jurisdictions": ["IN"],
  "instrument_type": "wire_transfer",
  "customer_type": "institutional",
  "transaction_type": "cross_border_payment"
}
```

**Agent Flow:**
1. **Classify** → Applicable frameworks: RBI (cross-border + KYC)
2. **Retrieve** → RAG returns: RBI KYC Master Direction §3.3 ("Cross-border to non-KYC-verified entity >$1M → escalate to MLRO")
3. **Cross-Reference** → No conflicts (only RBI applies)
4. **Score Risk** → `_score_cross_border_payment()`:
   - counterparty_kyc_status == "not_verified" ✓
   - amount ($2M) > USD 1M threshold ✓
   - jurisdiction high-risk → **CRITICAL**
   - Required action: "Block transaction, escalate to MLRO per RBI KYC §3.3"
5. **Draft Narrative** → LLM narrates the CRITICAL rating (doesn't invent it)
6. **Verify Citations** → Confirms RBI-KYC-MASTER-DIRECTION#3.3 was retrieved ✓
7. **Finalize** → Return:
   ```json
   {
     "risk_rating": "CRITICAL",
     "rule_triggers": [
       {
         "rule_id": "RBI-KYC-CROSS-BORDER-THRESHOLD",
         "description": "Cross-border payment $2M to unverified KYC entity exceeds USD 1M escalation threshold",
         "severity": "CRITICAL",
         "citations": ["RBI-KYC-MASTER-DIRECTION#3.3@2016-02-25"]
       }
     ],
     "required_actions": ["Block transaction, escalate to MLRO"],
     "citations": [{ "citation_key": "rbi-kyc-master-direction#3.3@2016-02-25", "text": "..." }],
     "confidence_score": 0.95
   }
   ```

**Where Solution is Stored:**
- Rule logic: `code/agentic/tools/calculate_risk_rating.py::_score_cross_border_payment()`
- Regulations: `code/rag/corpus/sample_documents/rbi_kyc_master_direction.md`
- Assessment: `assessment_records` table + audit trail `audit_log_entries`

---

### Scenario 2: Large Intra-Group Derivative Exposure

**Transaction Input:**
```json
{
  "amount": 75000000,
  "currency": "USD",
  "counterparty": "FinServ Capital Markets (Singapore) Pte Ltd",
  "customer_type": "intra_group",
  "transaction_type": "derivative_trade",
  "instrument_type": "interest_rate_swap"
}
```

**Agent Flow:**
1. **Classify** → Frameworks: Basel III (large exposure rules)
2. **Retrieve** → Basel III §9.1 (25% Tier 1 limit), §9.3 (intra-group same rules), §9.4 (breach reporting)
3. **Score Risk** → `_score_derivative_trade()`:
   - Amount $75M, intra-group ✓
   - Exceeds assumed Tier 1 demo threshold → **HIGH**
   - Escalate for large-exposure review
4. **Finalize** → risk_rating: **HIGH**, required_actions: ["Perform large-exposure review per Basel III §9.1"]

**Where Solution is Stored:**
- Rule logic: `code/agentic/tools/calculate_risk_rating.py::_score_derivative_trade()`
- Regulations: `code/rag/corpus/sample_documents/basel_iii_large_exposures.md`

---

### Scenario 3: Regulatory Amendment Detection (FR-3)

**When Basel III 2023 amendment is ingested:**
1. Ingestion pipeline detects version change
2. Impact workflow diffs 2019 vs. 2023 documents
3. New §6.5 (Countercyclical Buffer 0-2.5%) identified
4. Maps to transaction types: capital-intensive transactions, derivative positions
5. Creates pending review item in `impact_review_items` table
6. Compliance Head reviews via `/api/v1/impact-review-queue` and marks resolved

**Where Solution is Stored:**
- Impact workflow: `code/agentic/impact/build_impact_graph.py`
- Review queue: `impact_review_items` table
- Documents: `code/rag/corpus/sample_documents/basel_iii_capital_adequacy_2023.md`

---

## Key Features Implemented

### ✅ Multi-Framework Compliance
- Basel III, MiFID II, RBI regulations ingested and searchable
- Cross-framework rule conflict detection
- Overlapping rules resolved to strictest interpretation

### ✅ Deterministic Risk Scoring
- Risk ratings never LLM-guessed — pure Python logic
- Scenario 1 (cross-border KYC): correctly rates CRITICAL
- Scenario 2 (large exposure): correctly rates HIGH
- Scenario 3 (retail investment): correctly requires appropriateness assessment
- Scenario 4 (NBFC PSL): correctly flags priority sector classification
- Ambiguous cases (unknown KYC status): floor at MEDIUM, never assume compliant

### ✅ Full Audit Trail
- Every transaction screening logged with retrieved regulations, model versions, confidence
- Auditors query by user, role, date, endpoint
- Compliance reports link back to audit trail entries

### ✅ Multi-Region Data Residency
- Separate Qdrant collections per region (IN/EU/US)
- Global regulations replicated into each region but tagged as GLOBAL
- No cross-region data movement

### ✅ Evaluation Framework
- 20-question ground-truth dataset covering all frameworks
- Citation accuracy (0.975, floor 0.90) confirms retrieved regulations match expected ones
- Risk-rating accuracy (4/4) confirms scoring logic
- One documented "hard" case failure (cross-framework question) explained honestly

### ✅ Production-Ready Code
- Enterprise package structure (separate rag/, llm/, agentic/, backend/)
- Type hints throughout (Pydantic models)
- Configuration via environment variables
- MVP/production provider swapping via config flags
- 66 passing tests (no external services required)
- End-to-end HTTP smoke test validates all endpoints

---

## Configuration & Customization

All heavy dependencies are swappable via `.env` flags. See `code/.env.example`:

```bash
# Pick embedding provider
EMBEDDING_PROVIDER=local_hash           # MVP: bag-of-words (zero deps)
# EMBEDDING_PROVIDER=tei                # Production: BAAI semantic embedding

# Pick LLM provider
LLM_ROUTER_PROVIDER=local_stub          # MVP: extractive, deterministic
# LLM_ROUTER_PROVIDER=vllm              # Production: Llama-3.1-8B router

LLM_GENERATION_PROVIDER=local_stub      # MVP: extractive, deterministic
# LLM_GENERATION_PROVIDER=vllm          # Production: Llama-3.1-70B generation

# Pick reranker
RERANKER_PROVIDER=lexical               # MVP: overlap heuristic
# RERANKER_PROVIDER=cross_encoder       # Production: BAAI cross-encoder

# Pick database
DATABASE_URL=sqlite:///fincompliance.db # MVP: SQLite (no setup)
# DATABASE_URL=postgresql://...         # Production: Postgres (cloud-managed)

# PII redaction
PII_REDACTION_PROVIDER=regex            # MVP: regex patterns
# PII_REDACTION_PROVIDER=presidio       # Production: Microsoft Presidio

# Topical guardrail
TOPICAL_RAIL_PROVIDER=keyword           # MVP: keyword matching
# TOPICAL_RAIL_PROVIDER=nemo            # Production: NeMo Guardrails
```

To use production providers:
```bash
pip install -r requirements-full.txt
export LLM_GENERATION_PROVIDER=vllm
export EMBEDDING_PROVIDER=tei
uvicorn backend.main:api --port 8080
```

---

## Testing & Validation

### Unit Tests (66 passing)

```bash
cd code
pytest -v  # Runs all tests across rag, llm, agentic, backend, eval, mcp
```

### Evaluation Metrics

```bash
python -m eval.run_evaluation
# Outputs:
# - Citation accuracy: 0.975 (19/20 QA pairs correctly cite retrieved regulations)
# - Risk-rating accuracy: 4/4 (all reference scenarios produce expected severity)
# - Detailed per-question breakdown with failure analysis
```

### End-to-End Smoke Test

```bash
python -m scripts.smoke_test
# Validates all FR-1..FR-4 endpoints over real HTTP
```

---

## Known Limitations (MVP)

1. **Retrieval Quality:** `local_hash` embeddings use bag-of-words, not semantic similarity. Cross-framework questions may under-rank secondary framework clauses. Mitigated by: stopword filtering + relevance floor (0.16).

2. **LLM Output:** `local_stub` is purely extractive — never hallucinates. By design, it only echoes retrieved context. For production, `vLLM` adapter provides generative capability while guardrails ensure numeric consistency.

3. **Large-Exposure Scoring:** Demo uses a flat $50M threshold instead of querying counterparty's actual Tier 1 capital (not in payload). Production would integrate capital inquiry service.

4. **Regulatory Corpus:** Sample includes 6 documents (Basel III 2019/2023, Large Exposures, MiFID II, RBI KYC, RBI PSL). Production would have 100+ documents covering all jurisdictions + regular update pipeline.

5. **Impact Workflow:** FR-3 creates pending review items but doesn't auto-apply policy changes (human-in-the-loop by design). Production might integrate workflow automation.

---

## Next Steps for Production

1. **Model Deployment:** Serve Llama-3.1-70B via vLLM on EKS GPU node pool
2. **Embedding Server:** Deploy BAAI/bge-large-en-v1.5 via HuggingFace TEI
3. **Database:** Migrate SQLite to managed PostgreSQL (AWS RDS)
4. **Vector Store:** Qdrant server mode on EKS (current: embedded SQLite)
5. **Regulatory Corpus:** Expand from 6 sample docs to production regulatory library
6. **CI/CD Pipeline:** Add pre-commit hooks, GitHub Actions for testing, deployment automation
7. **Observability:** Integrate Prometheus/Grafana, structured logging to CloudWatch, LLM tracing
8. **Keycloak Integration:** Replace dev JWT issuance with real OIDC login

---

## Support & Documentation

- **Backend Details:** See `code/backend/README.md`
- **RAG Pipeline:** See `code/rag/README.md`
- **LLM Orchestration:** See `code/llm/README.md`
- **Agentic Workflow:** See `code/agentic/README.md`
- **Evaluation:** See `code/eval/README.md`
- **MCP Server:** See `code/mcp/README.md`
- **Frontend:** See `code/frontend/README.md`

---

## Contact & Attribution

Built as an MVP technical assessment for the FinServ Global AI Architect role. All code is production-aware: enterprise structure, explicit trade-offs, type-safe, tested, and documented.
