# ADR-003: Build vs. Buy for the Orchestration Layer (Agentic Framework Choice)

**Status:** Accepted

## Context

`AGENT-1` requires an agentic framework to orchestrate the Compliance Assessment Agent: querying
the knowledge base, cross-referencing multiple regulations, pulling transaction data, and
producing a structured, auditable compliance assessment (`FR-2`). The framework choice has to
satisfy requirements that are somewhat in tension with typical "agent framework" design goals:

- **Auditability over autonomy:** the Internal Auditor persona (`01-business-context-and-personas.md`)
  needs to reconstruct exactly what the agent saw and decided at every step, for every historical
  run. A framework optimized for flexible, free-form multi-agent conversation makes this harder,
  not easier.
- **Predictability:** a compliance decision tool should follow a bounded, reviewable reasoning
  skeleton (`AGENT-1.7`), not open-ended autonomous planning that could take an unexpected path
  through tools.
- **State persistence & resumability** (`AGENT-2`): state must checkpoint at every transition and
  support resuming a failed run.
- **Open-source constraint**, same as everywhere else in this design.
- **"Build vs. buy":** the alternative to assembling an open-source framework ourselves is a
  commercial/managed agent platform — evaluated here as the "buy" side of the decision.

## Decision

**Build on LangGraph** (open source, MIT) — i.e., "build" using an open-source *library*, not
"buy" a managed/commercial agent platform, and not a from-scratch state machine either.

## Alternatives Considered

| Option | For | Against | Verdict |
|---|---|---|---|
| **CrewAI** | Open source, fast to prototype role-based multi-agent setups, good for exploratory agent design | Optimized for autonomous multi-agent *conversation* between role-playing agents — a good fit for open-ended collaborative tasks, a poor fit for a bounded compliance workflow where we want `classify → retrieve → cross_reference → score → draft → verify → finalize` to be an explicit, inspectable graph rather than an emergent conversation between agents; state/checkpointing story is less mature than LangGraph's for this use case | Rejected — the flexibility CrewAI optimizes for is a liability here, not an asset, given the auditability requirement |
| **AutoGen** | Open source, strong for complex multi-agent conversations, Microsoft-backed | Same core mismatch as CrewAI: conversation-centric, less naturally suited to a fixed-skeleton, checkpointed, single-purpose workflow; heavier framework surface than needed for one well-defined agent | Rejected for the same reason as CrewAI |
| **[PROPRIETARY/managed] A commercial agent platform (the "buy" option)** — e.g. a vendor-hosted agent-building/orchestration SaaS | Faster initial setup, vendor-managed reliability/scaling, built-in observability UI | Almost universally means the platform brokers or logs requests through vendor infrastructure — a data-residency and `SEC-3` problem by default; vendor lock-in on the orchestration layer, which the assignment explicitly warns against ("over-reliance... with no fallback"); licensing cost at 10K queries/day scale is non-trivial and not open source | Rejected — fails the open-source constraint and reintroduces exactly the external-data-path risk `ADR-002` just eliminated at the model layer; defeats the purpose if the orchestration layer routes regulated data through a vendor anyway |
| **Custom-built state machine (no framework)** | Maximum control, zero framework dependency/lock-in | Reinvents checkpointing, retry/error-handling primitives, and graph visualization that LangGraph already provides and are directly needed for `AGENT-2.2`/`AGENT-3.1`; slower to build and higher long-term maintenance cost for no clear benefit over an OSS library that already fits | Rejected — not worth the build cost when LangGraph's primitives map directly onto the requirements |
| **LangGraph (chosen)** | Explicit typed state graph (fits `AGENT-1.7`'s fixed skeleton directly); built-in Postgres-backed checkpointing (`AGENT-2.2`) gives the audit trail almost for free; supports human-in-the-loop interrupts natively (`AGENT-2.4`); same ecosystem as the LangChain components already used for chunking, reducing the number of distinct libraries in the stack | Less "autonomous" than CrewAI/AutoGen by design — but this is the correct trade-off here, not a limitation to work around; still requires us to write the domain-specific tools (`AGENT-1.2`–`AGENT-1.6`) ourselves, same as any framework would | **Selected** |

## Consequences

**Positive:**
- The audit trail (`SEC-2.3`) is largely a byproduct of LangGraph's checkpoint history rather
  than a separately engineered logging system — reduces the chance of a gap between "what the
  agent did" and "what got logged."
- The fixed-skeleton graph (`AGENT-1.7`) is easy to review, test node-by-node, and explain to a
  non-engineer (e.g., a Compliance Head asking "how does it decide the risk rating") — a direct
  answer to the assignment's "defensible trade-offs" bar.
- No orchestration-layer data path to a third party — consistent with `ADR-002`'s model-hosting
  decision; the whole reasoning pipeline stays inside FinServ's VPC.

**Negative / accepted trade-offs:**
- Less flexible than a free-planning agent if a future scenario genuinely needs open-ended
  multi-step reasoning outside the fixed skeleton (e.g., a novel investigative workflow) — would
  require extending the graph deliberately rather than getting it "for free" from an autonomous
  planner. Judged acceptable: compliance workflows benefit from predictability more than from
  emergent flexibility.
- Team must still design and maintain the tool implementations (`AGENT-1.2`–`AGENT-1.6`) — the
  framework provides orchestration primitives, not domain logic.

## Status

Accepted.
