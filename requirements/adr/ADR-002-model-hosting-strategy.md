# ADR-002: Model Hosting Strategy (Self-Hosted vs. API)

**Status:** Accepted

## Context

`LLM-1` requires selecting how the foundation models (router/classifier and generation tiers)
are served. FinServ's constraints are unusually decisive for this decision, more than for a
typical application:

- **Regulatory sensitivity (`SEC-3`):** regulatory document text and transaction data (some of
  which carries counterparty PII) must not leave FinServ's network to a third-party API by
  default. This is not a preference — the assignment names it explicitly as a design smell if
  unaddressed.
- **Open-source constraint:** models must be open-source/open-weight; if a proprietary/paid
  service is used, it must be flagged with an OSS alternative the prototype actually runs.
- **Cost at target scale:** 500 concurrent users / 10K queries/day (`INFRA-3`) — high enough that
  per-token API pricing and self-hosted infra costs are both material and worth comparing
  directly, not assumed.
- **Latency SLAs (`INFRA-4`):** P95 6s for full RAG+generation — achievable either way, but
  self-hosting requires deliberate autoscaling (`INFRA-2`) to hit it, since there's no vendor SLA
  to lean on.
- **Data residency (`SEC-1`):** inference must happen in the same region as the data it's
  processing; a hosting option must support per-region deployment, not a single global endpoint.

## Decision

**Self-host open-weight models (Llama-3.1-8B / Llama-3.1-70B) via vLLM on EKS GPU node pools, one
deployment per region.** This is the default and only path for any request that touches
regulated document text or transaction data.

## Alternatives Considered

| Option | For | Against | Verdict |
|---|---|---|---|
| **[PROPRIETARY] Closed-source API (e.g., a frontier hosted model)** | Best-in-class accuracy out of the box, zero hosting ops, instant scaling | Violates `SEC-3.1` by default (data leaves FinServ's network to a third party); violates the assignment's open-source constraint outright; per-token cost at 600M tokens/month (`INFRA-3`) is comparable-to-worse than self-hosting *and* still doesn't solve data residency even if paid for | **Rejected** as the default path. Not used anywhere regulated data is involved. |
| **[PROPRIETARY] AWS Bedrock hosting the same open-weight Llama models (managed)** | Removes GPU-fleet ops burden (autoscaling, driver/runtime patching, capacity planning) from the platform team; still keeps the *model* open-weight; supports VPC PrivateLink so data doesn't traverse the public internet | Still a paid, AWS-operated managed service layered over the model — flagged per the assignment's rule ("if a proprietary or paid service is referenced... provide an open-source alternative that the prototype uses"); less control over quantization/batching tuning than raw vLLM; another vendor dependency in the critical path | **Not used in the prototype; noted as a legitimate production option** if the platform team's GPU-ops capacity becomes the bottleneck rather than cost or data control. **[OSS ALTERNATIVE actually used: self-hosted vLLM]**, per `LLM-1.2`. |
| **Self-hosted open-weight models via vLLM (chosen)** | Full data-residency control (`SEC-1.1`, `SEC-3.1` — architecturally no external egress path); fully open-source; cost is infra-metered and predictable/optimizable via Reserved Instances (`INFRA-3`); full control over quantization, batching, and routing (`LLM-1.3`, `LLM-2`) | Platform team owns GPU fleet operations (driver updates, capacity planning, scaling tuning); cold-start and multi-GPU tensor-parallel serving is genuinely harder to operate well than calling an API; accuracy ceiling is bounded by the best available open-weight model, which may lag frontier closed models on some tasks | **Selected.** The ops burden is accepted because it's the only option that satisfies `SEC-3` structurally rather than by policy, and it's the only fully open-source-compliant path. |

## Consequences

**Positive:**
- `SEC-3.1`'s no-egress NetworkPolicy is *enforceable* because inference literally runs inside
  FinServ's VPC — compliance is architectural, not a promise about a third party's data handling.
- Cost is transferable to Reserved Instances/Savings Plans as usage stabilizes (`INFRA-3`),
  giving a clear cost-optimization lever that a metered API doesn't offer.
- Full control over the fallback chain (`LLM-2.4`) and quantization trade-offs (`LLM-1.3`).

**Negative / accepted trade-offs:**
- Requires real MLOps/platform capability (GPU autoscaling, vLLM operational knowledge) that a
  pure API integration would not — this is a genuine, ongoing staffing cost, stated honestly
  rather than hand-waved.
- Time-to-first-token for a brand-new model upgrade is slower than "change an API model string" —
  a new model requires capacity planning, quantization validation, and `OBS-2.3` eval-gate
  clearance before promotion.
- If FinServ's own platform team cannot sustain GPU fleet operations, Bedrock (the flagged
  alternative above) is the documented fallback path — this ADR is explicit that the decision is
  revisited if that operational assumption (`11-non-goals-and-assumptions.md` #2) doesn't hold.

## Status

Accepted. Bedrock remains a documented, not-yet-exercised fallback if GPU-ops capacity becomes
the binding constraint rather than cost or data control.
