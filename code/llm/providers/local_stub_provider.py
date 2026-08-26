"""MVP default generation provider: deterministic and purely extractive —
it never invents text that isn't already present in its own prompt.

This stands in for `llm/providers/vllm_provider.py` (self-hosted
Llama-3.1, LLM-1.1) so the MVP runs without a GPU. It works by parsing the
`[CONTEXT #n key=...]...[/CONTEXT]` and `[FACT ...]...[/FACT]` blocks that
every prompt template in `llm/prompts/` embeds — the same delimiters a real
model is instructed to read — and assembling a schema-valid JSON response
from them. Because it only ever echoes text already in its input, it is
structurally incapable of hallucinating, which doubles as a legitimate
LLM-2.4 degraded-mode fallback candidate, not just a test fixture.
"""

import json
import re

from pydantic import BaseModel

from llm.providers.base import LLMProvider, LLMResponse
from llm.response_models import NarrativeOutput, QaAnswerOutput

_CONTEXT_BLOCK = re.compile(r"\[CONTEXT #\d+ key=(?P<key>\S+)\]\s*(?P<text>.*?)\s*\[/CONTEXT\]", re.DOTALL)
_FACT_BLOCK = re.compile(r"\[FACT(?: [^\]]*)?\](?P<text>.*?)\[/FACT\]", re.DOTALL)
_FACT_ATTR = re.compile(r"\[FACT (?P<attrs>[^\]]*)\]")
_REFUSAL_TEXT = "insufficient information in the indexed corpus"


class LocalStubProvider(LLMProvider):
    model_id = "local-stub-extractive-v1"
    model_version = "1.0.0"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.0,
        response_schema: type[BaseModel] | None = None,
    ) -> LLMResponse:
        if response_schema is QaAnswerOutput or "[CONTEXT" in user_prompt:
            payload = self._answer_from_context(user_prompt)
        elif response_schema is NarrativeOutput or "[FACT" in user_prompt:
            payload = self._narrative_from_facts(user_prompt)
        else:
            payload = {"narrative": user_prompt[:280], "key_points": []}

        return LLMResponse(
            text=json.dumps(payload),
            model_id=self.model_id,
            model_version=self.model_version,
            input_tokens=len(user_prompt.split()),
            output_tokens=len(json.dumps(payload).split()),
        )

    @staticmethod
    def _answer_from_context(user_prompt: str) -> dict:
        contexts = _CONTEXT_BLOCK.findall(user_prompt)
        if not contexts:
            return {"answer": _REFUSAL_TEXT, "citations_used": []}

        sentences = []
        citations_used = []
        for key, text in contexts[:5]:
            first_sentence = re.split(r"(?<=[.;])\s+", text.strip())[0]
            sentences.append(f"{first_sentence.rstrip('.')} [{_display_from_key(key)}].")
            citations_used.append(key)

        return {"answer": " ".join(sentences), "citations_used": citations_used}

    @staticmethod
    def _narrative_from_facts(user_prompt: str) -> dict:
        facts = _FACT_BLOCK.findall(user_prompt)
        if not facts:
            return {"narrative": "No supporting facts were provided for narrative generation.", "key_points": []}

        rating_match = re.search(r"Risk rating:\s*(\w+)", user_prompt)
        rating_clause = f"This assessment is rated {rating_match.group(1)}. " if rating_match else ""

        key_points = [fact.strip() for fact in facts]
        narrative = rating_clause + " ".join(key_points)
        return {"narrative": narrative.strip(), "key_points": key_points}


def _display_from_key(citation_key: str) -> str:
    """Best-effort human-readable rendering of a `doc_id::clause@version`
    or `doc_id#clause@version` key for the stub's inline citation — the
    authoritative formatter is `shared.ids.format_citation_display`, used
    once real chunk metadata (not just the key string) is available.
    """
    doc_and_clause, _, version = citation_key.rpartition("@")
    doc_id, sep, clause_id = doc_and_clause.partition("::") if "::" in doc_and_clause else doc_and_clause.partition("#")
    if not sep:
        return citation_key
    return f"{doc_id} §{clause_id}, v:{version}"
