# Backend API

FastAPI application wiring FR-1..FR-5 over the `rag/`, `llm/`, and `agentic/` layers, plus
SEC-2 auth/audit logging.

## Endpoints (all under `/api/v1`, see `/docs` for the live OpenAPI UI)

| Endpoint | Requirement | Role(s) |
|---|---|---|
| `POST /auth/dev-token` | SEC-2.1 stand-in — **dev only** | none |
| `POST /qa` | FR-1 | compliance_officer, compliance_head |
| `POST /screening` | FR-2 | compliance_officer, compliance_head |
| `POST /reports` | FR-4 | compliance_head |
| `GET /reports/{id}/markdown`, `/pdf` | FR-4.4 | compliance_head, internal_auditor |
| `GET /impact-review-queue` | FR-3.4 | compliance_head |
| `GET /audit-log`, `/audit-log/{request_id}` | SEC-2.3 | internal_auditor |
| `GET /health` | — | none |

## Run it

```bash
# from the code/ directory, with the venv active
PYTHONPATH=. uvicorn backend.main:api --reload --port 8080
```

Startup auto-ingests `rag/corpus/sample_documents/` and seeds the 5 demo transactions
(idempotent — safe on every restart, see `backend/main.py::_seed_demo_data_if_empty`), so
`/qa` and `/screening` work immediately.

## Auth in a local/demo session

There's no Keycloak in this MVP (see `backend/core/security.py`'s module docstring) — mint
a token for whichever persona you want to act as:

```bash
curl -s -X POST http://localhost:8080/api/v1/auth/dev-token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "officer@finserv.test", "role": "compliance_officer"}'
```

Then pass it as `Authorization: Bearer <token>` on every other request. Roles: `compliance_officer`,
`compliance_head`, `internal_auditor`, `platform_admin` — see `requirements/07-security-compliance-requirements.md` SEC-2.2 for what each can access.

## Test it

```bash
pytest backend/tests -v
```
