import time

import pytest

from llm.providers.base import LLMProvider, LLMResponse
from llm.router import CircuitOpenError, LLMRouter


class _FailingProvider(LLMProvider):
    model_id = "failing"
    model_version = "0"

    def generate(self, **kwargs) -> LLMResponse:
        raise RuntimeError("simulated provider failure")


class _WorkingProvider(LLMProvider):
    model_id = "working"
    model_version = "1"

    def generate(self, **kwargs) -> LLMResponse:
        return LLMResponse(text='{"ok": true}', model_id=self.model_id, model_version=self.model_version)


def _routing_config(tmp_path, failure_threshold: int = 2, reset_timeout: float = 0.1) -> str:
    path = tmp_path / "routing.yaml"
    path.write_text(
        "tasks:\n  qa_answer: generation\n"
        f"circuit_breaker:\n  failure_threshold: {failure_threshold}\n  reset_timeout_seconds: {reset_timeout}\n"
    )
    return str(path)


def test_falls_back_to_secondary_provider_on_primary_failure(tmp_path):
    """LLM-2.4: primary -> secondary self-hosted fallback, no external API."""
    router = LLMRouter(routing_config_path=_routing_config(tmp_path))
    router.register_provider("generation", _FailingProvider())
    router.register_provider("generation", _WorkingProvider())

    response = router.generate("qa_answer", "system", "user")

    assert response.model_id == "working"


def test_circuit_opens_after_consecutive_failures_then_half_opens(tmp_path):
    # reset_timeout is deliberately small but the sleep below gives a wide
    # (10x) margin over it — a tight margin (e.g. 0.05/0.06) was flaky
    # under load in the full suite, since Windows scheduler jitter can
    # eat a few tens of milliseconds between the two calls.
    router = LLMRouter(routing_config_path=_routing_config(tmp_path, failure_threshold=2, reset_timeout=0.05))
    router.register_provider("generation", _FailingProvider())

    for _ in range(2):
        with pytest.raises(RuntimeError):
            router.generate("qa_answer", "system", "user")

    with pytest.raises(CircuitOpenError):
        router.generate("qa_answer", "system", "user")

    time.sleep(0.5)

    # Half-open: the call is allowed through again (and fails again, since
    # the only registered provider is still broken) instead of being
    # short-circuited a second time.
    with pytest.raises(RuntimeError):
        router.generate("qa_answer", "system", "user")


def test_no_registered_provider_raises_clear_error(tmp_path):
    router = LLMRouter(routing_config_path=_routing_config(tmp_path))
    with pytest.raises(RuntimeError, match="no LLM provider registered"):
        router.generate("qa_answer", "system", "user")
