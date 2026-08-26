# FinServ AI Regulatory Compliance Assistant — Code

A runnable slice of the architecture in [`../requirements/`](../requirements/): a RAG pipeline
over Basel III / MiFID II / RBI regulatory text, an agentic transaction-compliance checker, an
MCP tool server, a FastAPI backend, a thin demo UI, and an evaluation framework.

**This is an MVP.** Every heavy production dependency (the 70B/8B Llama models via vLLM, the
BAAI embedding/reranker models, Presidio, NeMo Guardrails, RAGAS's LLM-judged metrics, Apache
Airflow) is swapped for a lightweight, dependency-free stand-in by default, selected purely by
config — see [Provider matrix](#provider-matrix). This is what lets the whole stack run on a
laptop with `pip install` and no GPU, while every module is written against the same interface
the real component would use. Every stand-in's limitations are called out explicitly in the
relevant README or module docstring — see [Known MVP limitations](#known-mvp-limitations).

## Contents

- [Repository layout](#repository-layout)
- [Quickstart — zero-infra local](#quickstart--zero-infra-local)
- [Quickstart — docker compose](#quickstart--docker-compose)
- [Trying the API](#trying-the-api)
- [Running the MCP server](#running-the-mcp-server)
- [Running the evaluation framework](#running-the-evaluation-framework)
- [Testing](#testing)
- [Provider matrix](#provider-matrix)
- [Requirement traceability](#requirement-traceability)
- [Known MVP limitations](#known-mvp-limitations)
- [Troubleshooting](#troubleshooting)

## Repository layout

```
code/
├── shared/       Domain models, enums, config, logging, DB (SQLAlchemy) — imported by everything else
├── rag/          Ingestion, chunking, embeddings, vector store, hybrid retrieval        (RAG-1..7)
├── llm/          Provider abstraction, routing/fallback, prompts, guardrails            (LLM-1..4)
├── agentic/      LangGraph compliance-assessment agent, tools, FR-3 impact graph        (AGENT-1..4)
├── mcp/          MCP server exposing the agent's tools (fincompliance_mcp package)
├── backend/      FastAPI app — FR-1..FR-4 endpoints, SEC-2 auth/audit                   (FR-1..5, SEC-2)
├── frontend/     Thin React/TS demo UI (not rubric-scored, see its own README)
├── eval/         RAGAS + custom metrics against a 20-question ground-truth set          (EVAL-1..3)
├── infra/        Terraform/K8s reference skeleton (illustrative, not applied)
├── scripts/      seed_corpus.py, smoke_test.py
├── docker-compose.yml, Makefile-equivalent commands below, requirements*.txt
└── .env.example
```

Every package has its own README with the detail relevant to it; this file is the entry point.

## Quickstart — zero-infra local

No Docker, no GPU, no external services — SQLite + Qdrant's embedded mode + the `local_stub`
LLM/embedding providers.

```bash
cd code
python -m venv .venv

# Windows (PowerShell):        .venv\Scripts\Activate.ps1
# Windows (Git Bash), macOS/Linux:
source .venv/Scripts/activate   # Git Bash on Windows
# source .venv/bin/activate      # macOS/Linux

pip install -r requirements.txt
cp .env.example .env            # defaults already work; edit if you want to change ports/providers

# Ingest the sample regulatory corpus + seed 5 demo transactions
python -m scripts.seed_corpus

# Start the API (auto re-ingests/re-seeds on startup too, idempotently)
uvicorn backend.main:api --reload --port 8080
```

Open `http://localhost:8080/docs` for the live OpenAPI UI, or jump to
[Trying the API](#trying-the-api) below. In a second terminal, start the demo UI:

```bash
cd code/frontend
npm install
npm run dev
```

Open `http://localhost:5173`, sign in as any role (see `frontend/README.md` — there's no
Keycloak in this MVP, sign-in mints a demo JWT), and try the Q&A / Screening pages.

## Quickstart — docker compose

Closer to the target topology: Postgres (registry/audit), Qdrant (server mode), Redis, the
backend, the MCP server, and the frontend — still using `local_stub`/`local_hash` providers by
default (no GPU required; see [Provider matrix](#provider-matrix) to point it at real models).

```bash
cd code
cp .env.example .env
docker compose up --build
```

- Backend: `http://localhost:8080/api/v1` (`/docs` for OpenAPI)
- Frontend: `http://localhost:5173`
- MCP server (SSE): `http://localhost:8090`
- Qdrant dashboard: `http://localhost:6333/dashboard`

## Trying the API

The fastest way to see every FR-1..FR-4 endpoint exercised end-to-end (with real output, not a
transcript) is:

```bash
python -m scripts.smoke_test               # backend must already be running (see Quickstart)
```

Or by hand:

```bash
# 1. Mint a token for whichever persona you want to act as (SEC-2.2 roles)
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/dev-token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "officer@finserv.demo", "role": "compliance_officer"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. FR-1: ask a regulatory question
curl -s -X POST http://localhost:8080/api/v1/qa \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "What are the Tier 1 capital requirements under Basel III?", "jurisdictions": ["IN"]}'

# 3. FR-2: screen a transaction (reference scenario 1 — expect CRITICAL/HIGH, RBI KYC cited)
curl -s -X POST http://localhost:8080/api/v1/screening \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"amount": 2000000, "currency": "USD", "counterparty": "Meridian Offshore Holdings Ltd",
       "counterparty_kyc_status": "not_verified", "jurisdictions": ["IN"],
       "instrument_type": "wire_transfer", "customer_type": "institutional",
       "transaction_type": "cross_border_payment", "counterparty_jurisdiction_risk": "high"}'
```

The 4 sample scenarios from the assignment brief (plus a 5th ambiguous-input case) are seeded
as `TXN-1001`..`TXN-1005` — see `agentic/seed_data/transactions.json`, and drive them from the
frontend's Screening page with one click, or via the `screen_seeded_transaction` MCP tool.

`FR-4` (reports, `compliance_head` role) and the `SEC-2.3` audit trail (`internal_auditor`
role) follow the same pattern — see `backend/README.md` for the full endpoint table.

## Running the MCP server

```bash
cd code
PYTHONPATH=.:./mcp MCP_TRANSPORT=stdio python -m fincompliance_mcp.server
```

See `mcp/README.md` for why it needs two `PYTHONPATH` entries, and for wiring it into Claude
Desktop or another MCP client. Exposes `search_regulations`, `answer_compliance_question`,
`get_transaction_details`, `screen_transaction`, and `screen_seeded_transaction`.

## Running the evaluation framework

```bash
cd code
python -m eval.run_evaluation
```

Writes `eval/reports/latest.md` and `latest.json`. See `eval/README.md` for what each metric
means and why RAGAS's LLM-judged metrics report as skipped under the MVP default providers.

## Testing

```bash
cd code
pytest                       # backend + rag + llm + agentic + eval + mcp, ~65 tests, no external services needed
cd frontend && npm run typecheck
```

`conftest.py` at the repo root points the DB and vector store at a fresh temp location for the
whole test session, so `pytest` never touches your local `fincompliance.db` / `.qdrant_data`.

## Provider matrix

Every row below is a `.env` flag (see `.env.example`), never a code change — see each
package's README for the adapter code.

| Component | MVP default | Production adapter | Requirement |
|---|---|---|---|
| Embeddings | `EMBEDDING_PROVIDER=local_hash` | `tei` (BAAI/bge-large-en-v1.5 via HF TEI) | RAG-3.1 |
| Reranker | `RERANKER_PROVIDER=lexical` | `cross_encoder` (BAAI/bge-reranker-large) | RAG-4.3 |
| Compression | `COMPRESSION_PROVIDER=passthrough` | `llmlingua` | RAG-4.4 |
| Vector store | Qdrant embedded (`QDRANT_URL` unset) | Qdrant server | RAG-3.2 |
| LLM (router + generation) | `local_stub` (extractive, never hallucinates) | `vllm` (self-hosted Llama-3.1) | LLM-1.1, LLM-2 |
| PII redaction | `PII_REDACTION_PROVIDER=regex` | `presidio` | LLM-4.3 |
| Topical rail | `TOPICAL_RAIL_PROVIDER=keyword` | `nemo` (NeMo Guardrails) | LLM-4.5 |
| Checkpointer | `AGENT_CHECKPOINTER=memory` | `postgres` | AGENT-2.2 |
| Database | SQLite (`DATABASE_URL`) | Postgres / RDS | RAG-5.4 |

Install `requirements-full.txt` (on GPU-capable infrastructure) to make the production
adapters' dependencies available; see that file's header for why they're split out.

## Requirement traceability

Every module's docstring cites the requirement ID(s) it implements (`RAG-2.1`, `AGENT-1.5`,
`SEC-2.3`, ...) — cross-reference against [`../requirements/`](../requirements/) for the
rationale behind each. [`../requirements/CHECKLIST.md`](../requirements/CHECKLIST.md) tracks
what's done against the assignment's rubric.

## Known MVP limitations

Stated explicitly rather than discovered later, per
[`../requirements/11-non-goals-and-assumptions.md`](../requirements/11-non-goals-and-assumptions.md):

- **Retrieval quality is bag-of-words, not semantic.** `local_hash` embeddings and the
  `lexical` reranker are deterministic, dependency-free stand-ins (see `rag/README.md`) —
  good enough to demonstrate the pipeline's structure (chunking, hybrid fusion, filters,
  versioning, relevance floor) end-to-end, not MTEB-grade retrieval. A genuinely
  cross-framework question can under-rank a secondary framework's chunk relative to a
  dominant one (see `eval/reports/latest.md`'s one documented failure, `QA-16`).
- **The LLM never invents structured facts.** Risk ratings, citations, and required actions
  are deterministic Python (`agentic/tools/`); the LLM only narrates them. This means the
  MVP's `local_stub` provider — a purely extractive template-filler — is a legitimate
  functional stand-in, not just a test fixture; see `llm/README.md`.
- **AGENT-2.4 human-in-the-loop** is a `status=NEEDS_REVIEW` flag, not a literal paused-graph
  + resume API — see `agentic/graph/build_graph.py`'s module docstring.
- **Basel III large-exposure scoring** uses a flat demo notional threshold in place of the
  counterparty's actual Tier 1 capital (not in this payload/corpus) — see
  `agentic/tools/calculate_risk_rating.py`.
- **`infra/`** is a reference skeleton illustrating the target AWS/K8s topology; it is not
  `terraform apply`-able (no state backend, no real account) — see `infra/README.md`.
- Full list of assumptions/exclusions: `../requirements/11-non-goals-and-assumptions.md`.

## Troubleshooting

- **`ModuleNotFoundError` for `shared`/`rag`/`llm`/...** — run commands from inside `code/`
  (not the repo root), with the venv active. `pytest` and anything using `python -m` from
  `code/` resolve this automatically; a plain `python somefile.py` from elsewhere will not.
- **`ModuleNotFoundError: fincompliance_mcp`** — the MCP server needs `code/mcp` on the path
  *in addition to* `code/`; see [Running the MCP server](#running-the-mcp-server).
- **Port already in use** — `8080` (backend), `5173` (frontend), `8090` (MCP/SSE), `6333`/`6334`
  (Qdrant), `5432` (Postgres), `6379` (Redis) are the defaults; change via `.env` / `docker-compose.yml`.
- **SQLite "database is locked" on Windows** — stop any other process still holding
  `fincompliance.db` (e.g. a background `uvicorn` from a previous run) before deleting it or
  switching `DATABASE_URL`.
- **A retrieval-dependent test seems to flake on first run** — the very first call against a
  fresh `.qdrant_data` directory pays Qdrant's embedded-storage initialization cost; re-run if
  you hit a timeout in a constrained environment.
