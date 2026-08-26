import llm.router as router_module
from llm.providers.base import LLMProvider, LLMResponse
from llm.providers.local_stub_provider import LocalStubProvider
from llm.response_models import QaAnswerOutput
from llm.router import LLMRouter
from llm.structured_output import GenerationDegraded, generate_structured


def _install_router(router: LLMRouter, monkeypatch) -> None:
    monkeypatch.setattr(router_module, "_router_singleton", router)


def test_generate_structured_parses_local_stub_output(tmp_path, monkeypatch):
    routing_path = tmp_path / "routing.yaml"
    routing_path.write_text("tasks:\n  qa_answer: generation\n")
    router = LLMRouter(routing_config_path=str(routing_path))
    router.register_provider("generation", LocalStubProvider())
    _install_router(router, monkeypatch)

    user_prompt = "[CONTEXT #1 key=doc_a::1@v1]\nBanks must hold 4.5% CET1.\n[/CONTEXT]"
    result = generate_structured(
        task="qa_answer",
        template_id="qa_answer",
        template_version="v1",
        system_prompt="system",
        user_prompt=user_prompt,
        response_model=QaAnswerOutput,
    )

    assert isinstance(result.parsed, QaAnswerOutput)
    assert "doc_a::1@v1" in result.parsed.citations_used


class _AlwaysInvalidProvider(LLMProvider):
    model_id = "invalid"
    model_version = "0"

    def generate(self, **kwargs) -> LLMResponse:
        return LLMResponse(text="not json at all", model_id=self.model_id, model_version=self.model_version)


def test_generate_structured_raises_generation_degraded_after_bad_retry(tmp_path, monkeypatch):
    routing_path = tmp_path / "routing.yaml"
    routing_path.write_text("tasks:\n  qa_answer: generation\n")
    router = LLMRouter(routing_config_path=str(routing_path))
    router.register_provider("generation", _AlwaysInvalidProvider())
    _install_router(router, monkeypatch)

    try:
        generate_structured(
            task="qa_answer",
            template_id="qa_answer",
            template_version="v1",
            system_prompt="system",
            user_prompt="question with no context blocks",
            response_model=QaAnswerOutput,
        )
        raised = False
    except GenerationDegraded:
        raised = True

    assert raised
