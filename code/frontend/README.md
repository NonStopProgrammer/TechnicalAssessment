# Frontend (thin demo UI)

A minimal React + TypeScript + Vite UI exercising FR-1/FR-2/FR-4 and the SEC-2.3 audit
trail. Explicitly **not** a rubric-scored deliverable (see
`requirements/11-non-goals-and-assumptions.md`) — it exists so the backend is demoable
without `curl`, not as a polished product UI.

## Run it

```bash
cd frontend
npm install
npm run dev
```

Opens on `http://localhost:5173`, talking to the backend at `VITE_API_BASE_URL`
(defaults to `http://localhost:8080/api/v1` — copy `.env.example` to `.env.local` to
override).

## Sign-in

There's no real login screen because there's no Keycloak in this MVP (see
`backend/core/security.py`) — the login page mints a demo JWT for whichever persona
(role) you pick. Switch roles by logging out and back in as a different role to see the
RBAC boundaries (e.g. only `internal_auditor` can open Audit Trail; only
`compliance_head` can generate a Report).

## Pages

| Page | Requirement |
|---|---|
| Q&A | FR-1 |
| Screening (with one-click reference scenarios) | FR-2 |
| Reports | FR-4 |
| Audit Trail | SEC-2.3 |

## Typecheck

```bash
npm run typecheck
```
