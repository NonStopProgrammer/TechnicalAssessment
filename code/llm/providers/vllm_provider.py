"""LLM-1.1 production adapter: self-hosted Llama-3.1 served by vLLM behind
its OpenAI-compatible `/chat/completions` endpoint, inside the `inference`
namespace with no outbound internet route (SEC-3.1) — this class never
calls anything but `base_url`.

Activate with LLM_ROUTER_PROVIDER=vllm / LLM_GENERATION_PROVIDER=vllm once
vLLM is reachable (see requirements/06-infrastructure-nfr-requirements.md
INFRA-1.2 for the GPU node pools this targets). LLM-3.5 structured output
uses vLLM's guided-decoding `extra_body.guided_json` so the response is
schema-valid by construction, not just by instruction.
"""

import httpx
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from llm.providers.base import LLMProvider, LLMResponse


class VLLMProvider(LLMProvider):
    def __init__(self, base_url: str, tier: str, model_id: str | None = None, model_version: str = "unpinned"):
        self.base_url = base_url.rstrip("/")
        self.tier = tier
        self.model_id = model_id or (
            "meta-llama/Llama-3.1-8B-Instruct" if tier == "router" else "meta-llama/Llama-3.1-70B-Instruct"
        )
        self.model_version = model_version

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.0,
        response_schema: type[BaseModel] | None = None,
    ) -> LLMResponse:
        body: dict = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_schema is not None:
            # vLLM guided-decoding extension — LLM-3.5.
            body["extra_body"] = {"guided_json": response_schema.model_json_schema()}

        data = self._post_with_retry(body)
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return LLMResponse(
            text=choice["message"]["content"],
            model_id=self.model_id,
            model_version=self.model_version,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            finish_reason=choice.get("finish_reason", "stop"),
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=3),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    def _post_with_retry(self, body: dict) -> dict:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(f"{self.base_url}/chat/completions", json=body)
            response.raise_for_status()
            return response.json()
