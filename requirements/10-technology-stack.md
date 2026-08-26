# Consolidated Technology Stack

Every choice below is **open source** unless marked **[PROPRIETARY]**, in which case an
**[OSS ALTERNATIVE]** the prototype actually uses is given right next to it, per the assignment's
hard constraint. This is the single source of truth for "what do we build with" — the PPT in
`docs/` visualizes this table plus the architecture it implies.

## Layer-by-layer

| Layer | Choice | License/type | Why (1-liner — full rationale in the linked requirement/ADR) |
|---|---|---|---|
| Cloud provider | **AWS** (EKS, S3, RDS, ElastiCache, KMS) | Commercial cloud, infra is metered but the *software stack on it* is OSS | Regions in all 3 markets; see `06-infrastructure-nfr-requirements.md` |
| Container orchestration | **Kubernetes (EKS)** + Helm | Apache 2.0 (K8s) | Industry standard, per-region cluster isolation (`INFRA-1.1`) |
| Node/pod autoscaling | **Karpenter** + **KEDA** | Apache 2.0 | GPU-aware, queue-depth-based scaling (`INFRA-2`) |
| Service mesh | **Istio** | Apache 2.0 | mTLS + network policy enforcement for `SEC-3.1` |
| Document parsing | **Unstructured.io** | Apache 2.0 | Layout-aware multi-format parsing (`RAG-1.1`) |
| Data pipeline orchestration | **Apache Airflow** (self-hosted) | Apache 2.0 | Ingestion + eval + impact-scan DAGs (`RAG-1.5`, `OBS-2.1`) — see `ADR` topic candidates |
| Chunking / RAG glue | **LangChain** components (`RecursiveCharacterTextSplitter`, etc.) | MIT | `RAG-2` |
| Embedding model | **BAAI/bge-large-en-v1.5** | MIT (open weights) | `RAG-3.1` — self-hosted via HuggingFace TEI |
| Re-ranker | **BAAI/bge-reranker-large** | MIT (open weights) | `RAG-4.3` |
| Context compression | **LLMLingua** | MIT | `RAG-4.4` |
| Vector database | **Qdrant** (self-hosted) | Apache 2.0 | Native hybrid search + payload filters; full analysis in `ADR-001` |
| Keyword/sparse signal | Qdrant native sparse vectors (BM25/SPLADE-style) | Apache 2.0 | Avoids running a second search cluster (OpenSearch) just for BM25 |
| Foundation models | **Llama-3.1-8B-Instruct** (router) + **Llama-3.1-70B-Instruct** (generation) | Llama 3.1 Community License (open-weight) | `LLM-1.1` |
| Model serving | **vLLM** | Apache 2.0 | High-throughput self-hosted serving, structured-output support (`LLM-3.5`) |
| [PROPRIETARY] managed hosting alternative | AWS Bedrock (same open-weight models, managed) | Paid AWS service | **[OSS ALTERNATIVE used in prototype: self-hosted vLLM]** — `LLM-1.2`, `ADR-002` |
| Agent orchestration | **LangGraph** | MIT | Explicit state graph → auditability (`AGENT-1.1`, `ADR-003`) |
| Guardrails — topical/scope | **NeMo Guardrails** | Apache 2.0 | `LLM-4.5` |
| Guardrails — output schema | **Pydantic** / `outlines` guided generation | MIT/Apache 2.0 | `LLM-3.5`, `LLM-4.2` |
| Guardrails — PII redaction | **Microsoft Presidio** | MIT | `LLM-4.3` |
| Response cache | **GPTCache** | MIT | `LLM-2.5` |
| Evaluation | **RAGAS** + custom metrics | Apache 2.0 | `09-evaluation-framework-requirements.md` |
| Auth | **Keycloak** (OIDC) | Apache 2.0 | `SEC-2.1` |
| Relational store (registry/audit metadata) | **PostgreSQL** (Amazon RDS, managed) | PostgreSQL license (OSS engine, managed hosting) | Holds no raw regulated document text, only metadata (`RAG-5.4`, `SEC-2.3`) |
| Cache | **Redis** (Amazon ElastiCache, managed) | BSD (engine, managed hosting) | Session/response cache |
| Metrics | **Prometheus** + **Grafana** | Apache 2.0 | `OBS-1.1` |
| LLM tracing/cost | **Langfuse** (self-hosted) | MIT | `OBS-1.2` |
| API framework | **FastAPI** | MIT | REST endpoints for `FR-1`–`FR-4` |
| IaC | **Terraform** | BUSL (source-available; free for this use) | Cluster/infra provisioning |
| CI/CD | **GitHub Actions** | — | Build/test/deploy pipeline (future dev phase) |

## Where a managed AWS service is used despite being "not OSS software"

These are infrastructure/hosting choices, not model/library choices, and none of them touch raw
regulated document text or hold it as their primary content — flagged here for transparency
since the assignment's constraint is about the AI components (data, models, libraries):

- **RDS (Postgres), ElastiCache (Redis):** managed hosting of open-source database engines.
  Holds metadata/audit/cache, not the regulatory document corpus itself (which lives in
  self-hosted Qdrant + S3).
- **EKS control plane:** managed Kubernetes control plane; all workloads on it are the OSS stack
  above.
- **KMS, Secrets Manager, ALB/WAF:** standard cloud plumbing (encryption, secrets, ingress), not
  AI-specific.

The one place a genuinely AI-specific proprietary service was considered and explicitly not used
is **LLM-1.2** (Bedrock as a hosting option for the same open-weight models) — called out with its
OSS alternative as the assignment requires.

## Consistency check against "What We Do NOT Want" (assignment, verbatim concerns)

| Concern raised by the assignment | How this stack avoids it |
|---|---|
| Generic LangChain tutorial repackaged as architecture | LangChain used only for chunking/text-splitting utilities; retrieval, agent orchestration, guardrails, and serving are each a purpose-fit OSS component (Qdrant, LangGraph, NeMo Guardrails, vLLM), not a single framework doing everything |
| Over-reliance on a single LLM provider, no fallback/cost controls | Two-tier self-hosted models + fallback chain + circuit breaker (`LLM-2.4`) + token budgets/caching (`LLM-2.5`) — "provider" here is FinServ's own infra, and even that has an internal fallback chain |
| Ignoring data sovereignty | Region-pinned deployment (`SEC-1.1`), no-egress inference namespace (`SEC-3.1`) — addressed structurally, not just in a policy doc |
