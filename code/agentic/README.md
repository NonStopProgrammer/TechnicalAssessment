# Agentic Compliance Workflow

Implements `requirements/05-agentic-workflow-requirements.md` (AGENT-1..AGENT-4).

```
state.py       AGENT-2.1 typed state (LangGraph state schema)
tools/         AGENT-1.2..1.6 — search, transaction lookup, cross-reference, risk
               scoring, citation bundling. Deterministic except search_regulations.
graph/         AGENT-1.7 fixed-skeleton graph + AGENT-2.2 checkpointing
impact/        FR-3's separate, simpler regulatory-change-impact graph
seed_data/     AGENT-1.3 mocked transaction store (the assignment's 4 scenarios + 1 ambiguous case)
```

## The graph

```
classify_input -> retrieve -> cross_reference -> score_risk -> draft_assessment
                                                                      ^     |
                                                          retry (<=1) |     v
                                                                  verify_citations
                                                                       |
                                                            (max steps)|  (ok)
                                                                       v     v
                                                                   degraded  finalize
```

Risk rating, rule triggers, and required actions are **always** computed by
`tools/calculate_risk_rating.py` — deterministic Python, never the LLM (AGENT-1.5).
The LLM's only role in this graph is `draft_assessment`: turning an already-correct
rating into readable prose. See `llm/README.md`'s design note.

## Try it

```bash
python -m scripts.seed_corpus                 # ingest the sample regulatory corpus
python -c "
from agentic.tools.get_transaction_details import get_transaction_details, seed_transactions
from agentic.graph.build_graph import run_screening
seed_transactions()
t = get_transaction_details('TXN-1001')
a = run_screening(t, request_id='demo-1')
print(a.risk_rating, a.status)
for c in a.citations: print(' -', c.display)
"
```

## Known MVP simplifications (stated explicitly, not hidden — see `requirements/11-non-goals-and-assumptions.md`)

- **AGENT-2.4 human-in-the-loop** is a `status=NEEDS_REVIEW` flag on a fully-computed
  assessment, not a literal LangGraph `interrupt()` pause + resume API. See the module
  docstring in `graph/build_graph.py` for the production upgrade path.
- **Basel III large-exposure check** compares the transaction amount to a flat demo
  notional threshold, not the counterparty's actual Tier 1 capital (not available in this
  payload/corpus) — see `tools/calculate_risk_rating.py`'s module docstring.
- **Cross-framework conflicts** (`AGENT-3.5`) are fully implemented and unit-tested
  (`tests/test_tools.py`), but the 4 reference scenarios don't naturally trigger one since
  the sample corpus's frameworks are complementary rather than numerically overlapping.
