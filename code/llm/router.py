"""LLM-2: multi-model routing.

Task -> tier assignment is config-driven (LLM-2.3, `llm/config/model_routing.yaml`).
Within a tier, LLM-2.4's fallback chain tries providers in registration
order (primary self-hosted model, then a smaller/local fallback) and opens
a circuit breaker after N consecutive failures, returning a structured
degraded signal rather than hammering a downed service. No tier ever falls
back to an external SaaS API for a task touching regulated content — see
`_build_default_router` below, which only ever wires self-hosted/local
providers.
"""

import time
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel

from llm.providers.base import LLMProvider, LLMResponse
from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)


class CircuitOpenError(Exception):
    """LLM-2.4: circuit is open for this tier — caller must degrade, not retry."""


class _CircuitBreaker:
    def __init__(self, failure_threshold: int, reset_timeout_seconds: float):
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold:
            self._opened_at = time.monotonic()

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self.reset_timeout_seconds:
            self._opened_at = None  # half-open: let the next call through as a trial
            self._consecutive_failures = 0
            return False
        return True


@dataclass
class RoutedGeneration:
    response: LLMResponse
    tier: str
    template_id: str
    template_version: str


class LLMRouter:
    def __init__(self, routing_config_path: str | None = None):
        settings = get_settings()
        path = Path(routing_config_path or settings.llm_routing_config_path)
        config = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}

        self._task_tier: dict[str, str] = config.get("tasks", {})
        cb_config = config.get("circuit_breaker", {})
        self._cb_failure_threshold = cb_config.get("failure_threshold", 3)
        self._cb_reset_timeout = cb_config.get("reset_timeout_seconds", 60)
        self._breakers: dict[str, _CircuitBreaker] = {}
        self._providers: dict[str, list[LLMProvider]] = {}

    def register_provider(self, tier: str, provider: LLMProvider) -> None:
        """Registration order is the LLM-2.4 fallback order for that tier."""
        self._providers.setdefault(tier, []).append(provider)

    def tier_for_task(self, task: str) -> str:
        return self._task_tier.get(task, "generation")

    def _breaker_for(self, tier: str) -> _CircuitBreaker:
        if tier not in self._breakers:
            self._breakers[tier] = _CircuitBreaker(self._cb_failure_threshold, self._cb_reset_timeout)
        return self._breakers[tier]

    def generate(
        self,
        task: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel] | None = None,
        **kwargs,
    ) -> LLMResponse:
        tier = self.tier_for_task(task)
        providers = self._providers.get(tier, [])
        if not providers:
            raise RuntimeError(f"no LLM provider registered for tier '{tier}'")

        breaker = self._breaker_for(tier)
        if breaker.is_open:
            raise CircuitOpenError(f"circuit open for tier '{tier}' after repeated failures")

        last_error: Exception | None = None
        for provider in providers:
            try:
                response = provider.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_schema=response_schema,
                    **kwargs,
                )
                breaker.record_success()
                return response
            except Exception as exc:  # noqa: BLE001 — try the next fallback provider
                last_error = exc
                logger.warning(
                    "llm.provider_failed", tier=tier, task=task, provider=type(provider).__name__, error=str(exc)
                )

        breaker.record_failure()
        raise RuntimeError(f"all providers for tier '{tier}' failed: {last_error}") from last_error


_router_singleton: LLMRouter | None = None


def get_router() -> LLMRouter:
    global _router_singleton
    if _router_singleton is None:
        _router_singleton = _build_default_router()
    return _router_singleton


def reset_router() -> None:
    """Test hook — forces the next get_router() call to rebuild from current settings."""
    global _router_singleton
    _router_singleton = None


def _build_default_router() -> LLMRouter:
    settings = get_settings()
    router = LLMRouter()

    router.register_provider("router", _build_provider(settings.llm_router_provider, settings.vllm_router_url, "router"))
    router.register_provider(
        "generation", _build_provider(settings.llm_generation_provider, settings.vllm_generation_url, "generation")
    )

    # LLM-2.4: a same-tier, always-available local fallback behind whatever
    # the primary is, so a vLLM outage degrades to extractive-but-cited
    # rather than a hard failure. Never an external SaaS fallback (SEC-3).
    from llm.providers.local_stub_provider import LocalStubProvider

    if settings.llm_router_provider != "local_stub":
        router.register_provider("router", LocalStubProvider())
    if settings.llm_generation_provider != "local_stub":
        router.register_provider("generation", LocalStubProvider())

    return router


def _build_provider(provider_name: str, url: str, tier: str) -> LLMProvider:
    if provider_name == "vllm":
        from llm.providers.vllm_provider import VLLMProvider

        return VLLMProvider(base_url=url, tier=tier)

    from llm.providers.local_stub_provider import LocalStubProvider

    return LocalStubProvider()
