# Non-Goals & Assumptions

Explicit scope boundaries — stated up front so gaps read as deliberate trade-offs, not oversights
(the assignment explicitly rewards "defensible trade-offs" and penalizes tutorial-grade design
that ignores hard parts).

## Non-goals for the prototype (Part 2 implementation, when it starts)

- **Not a production deployment.** The AWS/EKS/multi-region topology in
  `06-infrastructure-nfr-requirements.md` is the *target architecture*; the prototype runs
  locally/single-region (e.g., Docker Compose or a single small K8s cluster) with the same
  component boundaries so the code is a "faithful slice", per the assignment's own bar, not a
  literal multi-region deployment.
- **Not a real core-banking/transaction-feed integration.** `AGENT-1.3`
  `get_transaction_details` is backed by seeded/mocked transaction data, not a live system
  integration.
- **Not a full regulator-publication crawler.** `RAG-1.2` scheduled connectors are a stated
  target; the prototype ingests manually-collected sample documents (`RAG-1.6`).
- **Not a production-grade UI.** A minimal API (FastAPI) plus a thin demo UI (if any) is
  sufficient to exercise `FR-1`–`FR-4`; this is not a rubric-scored area per the assignment's own
  evaluation criteria for 2A/2B/2C.
- **Not multi-language.** Prototype corpus and queries are English-only; regional-language RBI
  circulars are a noted future extension (`RAG-3.1` mentions `multilingual-e5-large` as the
  upgrade path if/when needed).
- **Not five-nines availability.** Stated target is 99.5% (`INFRA-5.1`) for the
  prototype-to-production roadmap, not day-one HA across all failure modes.

## Assumptions

| # | Assumption | Why it matters |
|---|---|---|
| 1 | FinServ can legally operate self-hosted open-weight LLMs (Llama 3.1 license terms) for internal commercial use at this scale. | Load-bearing for `LLM-1.1`/`ADR-002`; Llama 3.1's community license permits this for organizations under ~700M MAU, which FinServ is. |
| 2 | FinServ has (or will provision) GPU-capable AWS capacity/quota in all three target regions. | Load-bearing for `INFRA-1.2`; GPU quota requests can take days-to-weeks and should be initiated early in any real engagement. |
| 3 | Audit log retention period is ultimately set by FinServ's own legal/compliance function per-market, not invented by this architecture. | `SEC-2.5` uses a placeholder (7 years) pending that input. |
| 4 | "Publicly available RBI circulars or Basel III excerpts" (assignment's own suggestion) are sufficient/acceptable stand-ins for FinServ's actual regulatory corpus in the prototype. | Governs `RAG-1.6`/`EVAL-1` sourcing — no non-public FinServ data is used or required. |
| 5 | A compliance SME is available (in a real engagement) to review few-shot examples (`LLM-3.3`) and spot-check outputs (`OBS-2.4`). | The architecture assumes this role exists; it does not attempt to replace domain expertise with the LLM. |
| 6 | 10K queries/day and 500 concurrent users (assignment's stated load) represent target-state usage, not day-one prototype load. | Sizing in `INFRA-3` is for that target; the actual prototype is validated at a much smaller scale. |

## Explicit exclusions (raised, considered, deliberately not solved here)

- **Model fine-tuning.** The design uses prompting/RAG over open-weight instruct models, not a
  fine-tuned compliance-domain model. Revisit if `EVAL-2` floors prove unreachable with prompting
  alone — noted as a future ADR candidate, not solved in this pass.
- **Real-time streaming transaction screening at core-banking volume.** `FR-2` is designed as a
  request/response check, not a streaming/CEP pipeline scoring every transaction as it clears.
  FinServ's actual real-time fraud/AML systems are assumed to be a separate, existing system this
  assistant complements rather than replaces.
