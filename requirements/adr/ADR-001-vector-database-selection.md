# ADR-001: Vector Database Selection

**Status:** Accepted

## Context

The RAG pipeline (`03-rag-pipeline-requirements.md`) needs a vector database that:

- Supports **hybrid search** (dense + sparse/keyword) natively — regulatory queries mix semantic
  intent with exact-term/number anchors (`RAG-4.1`).
- Supports rich **payload filtering** (jurisdiction, framework, version, effective date) applied
  *before* similarity scoring, not after (`RAG-4.5`), since a US-market query must never surface
  RBI-only content.
- Supports **document versioning** without hard deletes — old versions are marked superseded,
  not removed, to support point-in-time queries (`RAG-5`).
- Can be **self-hosted entirely within FinServ's VPC**, with no managed-service data path that
  could send document text outside the region (`SEC-1.1`, `SEC-3.1`) — this rules out any
  vector DB whose only production-grade offering is a third-party-hosted SaaS.
- Must be **open source** (assignment's hard constraint).
- Needs to scale to a multi-year corpus (200+ new circulars/year, `01-business-context-and-personas.md`)
  without a redesign.

## Decision

Use **Qdrant** (Apache 2.0), self-hosted on EKS (`INFRA-1.6`), one logical deployment per region.

## Alternatives Considered

| Option | For | Against | Verdict |
|---|---|---|---|
| **Weaviate** | Also OSS, also native hybrid search, mature GraphQL/REST API, strong module ecosystem | Heavier operational footprint (more moving parts — modules, separate inference containers for some features); hybrid search tuning (alpha parameter) less transparent than Qdrant's explicit RRF fusion | Close second; would be an equally defensible choice — not selected because Qdrant's simpler single-binary ops model reduces day-2 burden for a lean platform team |
| **Milvus** | Best-in-class raw ANN performance at very large scale (billions of vectors), strong for pure-scale use cases | Heaviest operational footprint of the three (etcd + Pulsar/Kafka + MinIO + query/data/index nodes) — the corpus here is thousands-to-low-millions of chunks, not billions of vectors, so Milvus's scale advantage isn't needed and its ops cost isn't justified | Rejected — over-engineered for this corpus size |
| **pgvector (on the existing Postgres)** | No new system to operate — reuses the Postgres already needed for `RAG-5.4`'s document registry; simplest possible ops story | No native sparse/hybrid search (would require bolting on a separate BM25 mechanism, e.g. `tsvector`, and fusing results in application code); ANN performance/recall at this corpus's growth trajectory (200+ docs/year compounding over years) degrades faster than a purpose-built vector engine as filters and payload complexity grow | Rejected for the *primary* index, but genuinely reconsidered — see Consequences |
| **Pinecone** | Excellent hybrid search and managed ergonomics | **[PROPRIETARY]** SaaS-only, no self-hosted option — directly violates `SEC-3.1` (regulated document text would leave FinServ's VPC to a third-party service) and the assignment's open-source constraint | Rejected outright — not viable given data sovereignty requirements |

## Consequences

**Positive:**
- Single self-hosted binary/StatefulSet keeps operational surface small for a platform team also
  running Airflow, vLLM, and the agent layer.
- Native RRF-based hybrid search and payload filtering map directly onto `RAG-4.1`/`RAG-4.5`
  without application-side fusion logic.
- Snapshot/restore model gives a clean story for `RAG-5.5` version rollback and `OBS-3.3`
  blue/green re-embedding cutover.

**Negative / accepted trade-offs:**
- Smaller ecosystem/community than Weaviate or Milvus — fewer third-party integrations,
  occasionally means writing a thin adapter ourselves.
- If corpus growth radically exceeds projections (multi-billion-chunk scale), Milvus's
  purpose-built distributed architecture would eventually out-scale Qdrant; this is judged
  unlikely for a compliance-document corpus (thousands of documents, not web-scale) and is
  revisited if `OBS-3.1` corpus-growth monitoring says otherwise.
- `pgvector` was genuinely close for the *metadata-adjacent* parts of the system; we keep
  Postgres as the registry-of-record (`RAG-5.4`) precisely so a future move is a re-index, not a
  re-architecture, if Qdrant is ever swapped out.

## Status

Accepted for the prototype and the target production architecture. Revisit if `OBS-3` drift
monitoring or corpus growth data contradicts the sizing assumptions above.
