# Infra (reference, not applied)

Illustrates the target topology from `requirements/06-infrastructure-nfr-requirements.md`
(INFRA-1..INFRA-5) and `requirements/07-security-compliance-requirements.md` (SEC-1, SEC-3).
**Not exercised by any test or CI step, and not `terraform apply`-able as-is** — there is no
AWS account behind this MVP. It exists so the code repository reflects the same
architecture the docs describe, not as a second, disconnected diagram.

```
terraform/   EKS cluster + node pool skeleton, one module invocation per region (INFRA-1.1)
k8s/         Namespace separation + NetworkPolicy (INFRA-1.3) and a vLLM Deployment example
             with a no-egress policy (SEC-3.1) — the concrete "inference pods cannot reach
             the internet" control the architecture doc asserts.
```

## What's real vs. illustrative

| Claim | Status |
|---|---|
| Namespace boundaries (`ingestion`/`retrieval`/`inference`/`agent`/`api`/`platform`) | Real YAML, matches `INFRA-1.3` exactly |
| `inference` namespace has no outbound route | Real `NetworkPolicy` YAML (`SEC-3.1`) — enforced by whatever CNI a real cluster runs, not tested here |
| 3-region EKS + Karpenter/KEDA autoscaling | Terraform module *shape* only — variables and resource blocks are illustrative, not a working root module (no state backend, no provider version lock, no real VPC/subnet wiring) |

If this MVP is ever promoted toward the target architecture, treat `terraform/` as a
starting skeleton to flesh out, not a deployable artifact.
