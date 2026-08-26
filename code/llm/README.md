# LLM Orchestration Layer

Implements `requirements/04-llm-orchestration-requirements.md` (LLM-1..LLM-4).

```
providers/    LLMProvider interface + local_stub (MVP) / vllm (production) adapters (LLM-1)
router.py     task -> tier routing, fallback chain, circuit breaker (LLM-2)
cache.py      token budget + semantic-ish response cache (LLM-2.5)
prompts/      versioned Jinja2 templates (LLM-3.1..3.4)
structured_output.py   schema-constrained generation + validate/retry (LLM-3.5, LLM-4.2)
guardrails/   PII redaction, citation verifier, topical rail, numeric consistency (LLM-4)
```

## Design note: the LLM never invents structured facts

Risk ratings, citations, and required actions are computed deterministically
(`agentic/tools/`) — the LLM's only job anywhere in this system is to turn
already-computed facts into readable prose (an answer grounded in retrieved
chunks, or a narrative explaining a rating). See `llm/response_models.py`
for why the output schemas are this narrow. This is also what makes
`llm/providers/local_stub_provider.py` viable as an MVP default: it is a
purely extractive template-filler, not a real generator, and the
architecture only ever asks it to narrate facts that are already correct.

## Try it

```bash
python -c "
from llm.structured_output import generate_structured
from llm.response_models import QaAnswerOutput
from llm.prompts.registry import render_prompt

prompt = render_prompt('qa_answer', query='What CET1 ratio must banks hold?', chunks=[
    type('C', (), {'citation_key': 'basel-iii-capital-adequacy-2023::6.1@2023-01-01',
                   'text': 'Banks must maintain a CET1 ratio of at least 4.5% of RWA.'})()
], as_of=None)
result = generate_structured('qa_answer', prompt.template_id, prompt.version,
                              prompt.system_prompt, prompt.user_prompt, QaAnswerOutput)
print(result.parsed)
"
```

## Provider matrix

See the root [README.md](../README.md#provider-matrix) for the full table — every row here
is a `.env` flag, not a code change.
