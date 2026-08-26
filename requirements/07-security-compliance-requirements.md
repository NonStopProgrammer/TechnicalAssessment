# Security & Compliance Requirements

Covers rubric item **1B.2 Security & Compliance**. This is the section the assignment explicitly
warns will be graded down for gaps ("What We Do NOT Want": ignoring data sovereignty).

---

## SEC-1 — Data residency & encryption

| ID | Requirement | Detail |
|---|---|---|
| SEC-1.1 | Region pinning | Documents/transactions tagged `jurisdiction=IN` are ingested, embedded, indexed, and queried only within `ap-south-1`; `jurisdiction=EU` within `eu-central-1`; `jurisdiction=US` within `us-east-1`. No cross-region replication of raw text or embeddings by default (`INFRA-1.1`, `INFRA-5.4`). |
| SEC-1.2 | Cross-jurisdiction query handling | A query that legitimately spans jurisdictions (e.g., a cross-border transaction touching both India and EU obligations, per `FR-2.2`) is served by querying each region's retrieval service independently and merging *citations/results*, not by centralizing the underlying documents in one region. |
| SEC-1.3 | Encryption at rest | AWS KMS customer-managed keys (per region, not shared) for S3 (raw documents), EBS (Qdrant volumes), RDS (registry/audit). |
| SEC-1.4 | Encryption in transit | TLS 1.2+ everywhere; internal service-to-service traffic additionally covered by Istio mTLS (`INFRA-1.4`), so encryption in transit doesn't depend solely on perimeter TLS termination. |
| SEC-1.5 | Key rotation | KMS automatic annual rotation minimum; documented process to force-rotate on suspected compromise. |

## SEC-2 — Model access controls & audit logging

| ID | Requirement | Detail |
|---|---|---|
| SEC-2.1 | AuthN | **Keycloak** (open source) OIDC provider; all API access requires an authenticated session, no anonymous access to any FR-1..FR-4 endpoint. |
| SEC-2.2 | AuthZ / RBAC | Roles map to personas: `compliance_officer` (query + screen), `compliance_head` (+ report generation, trend views), `internal_auditor` (read-only audit trail access, no query/screen access needed), `platform_admin` (ingestion, config, no access to raw query content). |
| SEC-2.3 | Audit log content | Every request logs: user id + role, endpoint, input (PII-redacted per `LLM-4.3`), retrieved chunk ids + versions, model id + version + prompt template version (`FR-5`), output, confidence score (`AGENT-3.3`), and any human override. This is the Internal Auditor persona's primary deliverable from the system. |
| SEC-2.4 | Tamper-evidence | Audit log rows written to Postgres (queryable) and mirrored to an S3 bucket with Object Lock (WORM) — an app-level bug or insider action cannot silently rewrite history. |
| SEC-2.5 | Retention | Audit logs retained per the longest applicable regulatory retention requirement across FinServ's markets (default posture: 7 years; exact figure to be confirmed with FinServ's own compliance team as an *input* to this system, not decided by the AI architecture itself — flagged as an assumption in `11-non-goals-and-assumptions.md`). |
| SEC-2.6 | Least privilege for service identities | Each K8s service account/IAM role scoped to only the AWS resources that service needs (e.g., the `inference` namespace's role has no S3/RDS access at all — it only serves model weights already loaded into the pod). |

## SEC-3 — No regulated data leaks to external LLM providers

This is the requirement the assignment calls out by name as a design smell if unaddressed.

| ID | Requirement | Detail |
|---|---|---|
| SEC-3.1 | Default posture: zero external calls for regulated content | `inference` namespace pods have **no outbound internet route** (enforced by NetworkPolicy + VPC route table, not just application config) — self-hosted vLLM serving is architecturally incapable of calling out, independent of any code-level mistake. |
| SEC-3.2 | If a managed/external service is ever used (e.g., `LLM-1.2` Bedrock fallback) | Must go through a PrivateLink/VPC endpoint (never public internet), must be logged identically to `SEC-2.3`, and must exclude any endpoint that touches raw regulatory document text or transaction PII unless explicitly allowlisted per task and reviewed. |
| SEC-3.3 | PII redaction before any logging/export path | `LLM-4.3` Presidio pass applies before data reaches caches, logs, or report exports — this is a control on the *outbound* side even for internal storage, not just external calls. |
| SEC-3.4 | Dependency/supply-chain check | Open-source models/libraries pulled from pinned, checksum-verified sources (HuggingFace with revision pinning, not "latest"); no model or library that phones home telemetry by default is used without disabling that telemetry — verified during `ADR-002` evaluation. |
| SEC-3.5 | Prompt-injection containment | Retrieved document content is treated as untrusted input to the LLM (a malicious/crafted circular could attempt instruction injection); `LLM-4.5` topical guardrail and structural output constraints (`LLM-3.5`) bound what an injected instruction could actually cause the system to do (it can't, e.g., trigger a tool call outside `AGENT-1`'s fixed skeleton). |

## SEC-4 — Input validation & data protection (cross-cutting)

| ID | Requirement | Detail |
|---|---|---|
| SEC-4.1 | Schema validation on every API boundary | `FR-2.1` and equivalents for all endpoints — reject early, don't let malformed input reach the LLM layer. |
| SEC-4.2 | Rate limiting | Per-user and per-IP, at the ALB/ingress layer, to bound both cost (`LLM-2.5`) and abuse surface. |
| SEC-4.3 | Secrets management | AWS Secrets Manager for DB credentials/API keys; never in config files or environment variables checked into version control. |
