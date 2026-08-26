"""LLM-3.5 (schema-constrained generation) + LLM-4.2 (validate-on-the-way-out
with one bounded retry, then graceful degradation) combined into the single
entry point callers use instead of talking to the router directly.
"""

import json
from dataclasses import dataclass
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from llm.providers.base import LLMResponse
from llm.router import CircuitOpenError, get_router
from shared.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class GenerationDegraded(Exception):
    """LLM-4.2: schema validation failed even after the bounded retry, or
    the circuit breaker was open — caller must fall back to an FR-1.5-style
    degraded response instead of forwarding a broken payload.
    """


@dataclass
class StructuredGeneration:
    parsed: BaseModel
    raw_response: LLMResponse
    template_id: str
    template_version: str


def generate_structured(
    task: str,
    template_id: str,
    template_version: str,
    system_prompt: str,
    user_prompt: str,
    response_model: type[T],
    max_tokens: int = 800,
    temperature: float = 0.0,
) -> StructuredGeneration:
    router = get_router()

    response = _call_router(router, task, system_prompt, user_prompt, response_model, max_tokens, temperature)
    parsed, error = _try_parse(response.text, response_model)
    if parsed is not None:
        return StructuredGeneration(parsed, response, template_id, template_version)

    logger.warning("llm.structured_output_retry", task=task, error=error)
    retry_prompt = (
        f"{user_prompt}\n\nYour previous response was invalid ({error}). "
        "Return ONLY a single valid JSON object matching the required schema."
    )
    response = _call_router(router, task, system_prompt, retry_prompt, response_model, max_tokens, temperature)
    parsed, error = _try_parse(response.text, response_model)
    if parsed is not None:
        return StructuredGeneration(parsed, response, template_id, template_version)

    raise GenerationDegraded(f"schema validation failed twice for task '{task}': {error}")


def _call_router(router, task, system_prompt, user_prompt, response_model, max_tokens, temperature) -> LLMResponse:
    try:
        return router.generate(
            task=task,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=response_model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except CircuitOpenError as exc:
        raise GenerationDegraded(str(exc)) from exc


def _try_parse(text: str, response_model: type[T]) -> tuple[T | None, str | None]:
    try:
        data = json.loads(text)
        return response_model.model_validate(data), None
    except (json.JSONDecodeError, ValidationError) as exc:
        return None, str(exc)
