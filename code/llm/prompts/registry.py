"""LLM-3.1: per-task templates stored as version-controlled Jinja2 files.
The version actually used is recorded in FR-5's provenance block by the
caller (see llm/router.py) — no silent "latest" resolution, matching
LLM-1.4's pinning philosophy applied to prompts as well as models.

File naming convention: `<task>.v<N>.jinja2`. Each file's rendered output
is split on a literal `---USER---` line into the LLM-3.2 system-prompt
contract (role/scope, citation format, refusal condition, output schema —
plus LLM-3.3 few-shot examples) and the per-request user prompt.
"""

from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES_DIR = Path(__file__).resolve().parent
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(disabled_extensions=(".jinja2",), default=False),
    trim_blocks=True,
    lstrip_blocks=True,
)

# Explicit pin, not directory-scanning "latest" — bump deliberately when a
# template changes, per LLM-3.1/LLM-1.4.
TEMPLATE_VERSIONS: dict[str, str] = {
    "qa_answer": "v1",
    "transaction_screening": "v1",
    "regulatory_diff": "v1",
    "report_narrative": "v1",
}


@dataclass
class RenderedPrompt:
    template_id: str
    version: str
    system_prompt: str
    user_prompt: str


def render_prompt(template_id: str, **context) -> RenderedPrompt:
    version = TEMPLATE_VERSIONS[template_id]
    template = _env.get_template(f"{template_id}.{version}.jinja2")
    rendered = template.render(**context)
    system_prompt, separator, user_prompt = rendered.partition("---USER---")
    if not separator:
        raise ValueError(f"template '{template_id}.{version}' is missing the '---USER---' delimiter")
    return RenderedPrompt(
        template_id=template_id,
        version=version,
        system_prompt=system_prompt.strip(),
        user_prompt=user_prompt.strip(),
    )
