# Infrastructure & Non-Functional Requirements

Covers rubric item **1B.1 Cloud Architecture**. Cloud chosen: **AWS**. Rationale: mature EKS/GPU
ecosystem, regions covering all three operating markets (`ap-south-1` Mumbai, `eu-central-1`
Frankfurt, `us-east-1`), and Bedrock available as a flagged managed fallback for open-weight
model hosting if self-hosting ops load ever needs relief (`LLM-1.2`). Azure/GCP were viable
alternatives; AWS is not a load-bearing choice elsewhere in the design — everything here ports
to Azure AKS / GCP GKE with equivalent managed-service substitutions.

---

## INFRA-1 — Deployment topology

| ID | Requirement | Detail |
|---|---|---|
| INFRA-1.1 | Kubernetes | **EKS**, one cluster per region (`ap-south-1`, `eu-central-1`, `us-east-1`) — not one global cluster — because data residency (`SEC-1`) requires that a region's regulated data and the inference/retrieval serving it never cross a border by default. |
| INFRA-1.2 | Node pools per cluster | (a) CPU pool: API services, Airflow, Qdrant, Postgres-adjacent workloads. (b) GPU pool A (`g5.2xlarge`, 1×A10G): 8B router/classifier model + embedding/rerank inference. (c) GPU pool B (`g5.12xlarge`, 4×A10G): 70B generation model (AWQ-quantized, tensor-parallel). |
| INFRA-1.3 | Namespace separation | `ingestion`, `retrieval`, `inference`, `agent`, `api`, `platform` (observability/guardrails) — separate namespaces with NetworkPolicies restricting cross-namespace traffic to declared paths only. |
| INFRA-1.4 | Service mesh | **Istio** (open source) for mTLS between services and fine-grained traffic policy — relevant because `inference` namespace pods must be provably unable to reach the public internet (`SEC-3`). |
| INFRA-1.5 | Ingress | AWS ALB Ingress Controller, TLS-terminated, WAF-attached for the public-facing API. |
| INFRA-1.6 | Stateful services | Qdrant (StatefulSet + EBS gp3, snapshotted to S3), Postgres (Amazon RDS for Postgres — managed, but holds no regulated document *text*, only metadata/registry/audit rows, so the managed-service trade-off is acceptable here unlike the LLM path), Redis (ElastiCache) for caching/session state. |

## INFRA-2 — Auto-scaling strategy for model inference endpoints

| ID | Requirement | Detail |
|---|---|---|
| INFRA-2.1 | Node-level autoscaling | **Karpenter** provisions/deprovisions GPU nodes on demand rather than static node groups — GPU capacity is the dominant cost driver, so idle GPU nodes overnight/off-hours are the single biggest avoidable spend. |
| INFRA-2.2 | Pod-level autoscaling | **KEDA**, scaling the vLLM deployments on a custom metric (in-flight request queue depth exposed by vLLM's metrics endpoint) rather than plain CPU/memory, which does not reflect GPU saturation. |
| INFRA-2.3 | Scale-to-floor, not scale-to-zero, for the generation tier | A minimum of 1 warm replica is always kept for the 70B tier — cold-starting a multi-GPU tensor-parallel model takes minutes, which blows the latency SLA (`FR-1.6`). The 8B router tier *can* scale toward zero off-hours (cheap, fast cold start). |
| INFRA-2.4 | Target concurrency | Sized for **500 concurrent users, 10,000 queries/day** (assignment's stated load) — see `INFRA-3` for the resulting cost model and the assumptions behind it. |

## INFRA-3 — Cost estimation (500 concurrent users, 10K queries/day)

**Assumptions:** 10K queries/day ≈ 420/hr average, but compliance-desk usage is bursty during
business hours across 3 time zones (India/EU/US) — so peak, not average, sizes the fleet.
Assume peak ≈ 4× average ≈ 1,700 queries/hr, average 1.5s of GPU time per query on the 70B tier
(quantized, batched via vLLM continuous batching) and 0.3s on the 8B tier for
routing/classification (every query hits the router; ~40% also hit the generation tier directly,
the rest are resolved by cache or a simpler path).

| Component | Sizing (peak) | Est. monthly cost (USD, us-east-1 on-demand-blended) |
|---|---|---|
| 70B generation GPU pool | 3–4× `g5.12xlarge` (4×A10G each), autoscaled 2–5 | ~$14,000–$18,000 |
| 8B router + embedding + reranker GPU pool | 2–3× `g5.2xlarge`, autoscaled 1–4 | ~$3,000–$4,500 |
| EKS control plane (×3 regions) | fixed | ~$220 |
| CPU node pool (API, Airflow, Qdrant, mesh) | ~6× `m6i.xlarge` blended across regions | ~$1,200 |
| Qdrant storage (EBS gp3 + S3 snapshots) | ~2TB across regions | ~$400 |
| RDS Postgres (registry/audit, Multi-AZ) | `db.r6g.xlarge` ×3 regions | ~$1,800 |
| ElastiCache Redis | small, caching only | ~$300 |
| Data transfer / ALB / WAF | | ~$500 |
| Observability stack compute (Prometheus/Grafana/Langfuse self-hosted) | | ~$600 |
| **Total (rough order-of-magnitude)** | | **~$22,000–$27,500/month** |
| Reserved-instance/Savings-Plan optimized (production, not day-1) | ~35–45% off GPU line items | **~$15,000–$18,000/month** |
| Cost-guardrail budget alert | | Hard alarm at 120% of the reserved-optimized estimate, paged to platform team |

**Why this beats a pay-per-token SaaS API at this volume:** ~10K queries/day × ~2K tokens
average context+generation ≈ 20M tokens/day ≈ 600M tokens/month. At a representative
frontier-model API rate (~$3–15 per million input/output tokens blended), that alone lands in a
comparable-to-higher monthly range *before* accounting for the fact that a SaaS API cannot
satisfy `SEC-3` (no regulated data leaves FinServ's network) at all — so for this workload the
self-hosted path is not just cheaper at scale, it's the only compliant option, which is the real
reason it's the default rather than cost alone (see `ADR-002`).

## INFRA-4 — Latency SLAs (referenced by FR-1.6, INFRA-2.3)

| Endpoint | P50 | P95 |
|---|---|---|
| `FR-1` Q&A (cache hit) | <500ms | <1.5s |
| `FR-1` Q&A (cache miss, full RAG+generation) | <3s | <6s |
| `FR-2` Transaction screening (full agent graph) | <8s | <15s |
| `FR-4` Report generation (async job, N transactions) | n/a — async | notified on completion, target <5 min for a 500-transaction monthly report |

## INFRA-5 — Availability & disaster recovery

| ID | Requirement | Detail |
|---|---|---|
| INFRA-5.1 | Target availability | 99.5% for the query/screening path in the prototype-to-production roadmap (not five-nines day one — stated honestly rather than aspirationally). |
| INFRA-5.2 | Multi-AZ within region | All stateful services Multi-AZ; GPU inference pods spread across AZs where capacity allows. |
| INFRA-5.3 | Backup | Qdrant snapshots + Postgres automated backups, both cross-AZ, retained 35 days; document registry is also re-derivable from the raw document store in S3 (source of truth), so vector index loss is recoverable, not catastrophic. |
| INFRA-5.4 | No cross-region DR for regulated data by default | A region outage degrades that region's service rather than failing over to another region's data store, because failing over would itself violate `SEC-1` — this is an explicit availability/compliance trade-off, stated so it isn't discovered during an incident. |
