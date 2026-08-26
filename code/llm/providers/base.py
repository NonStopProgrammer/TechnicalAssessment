"""LLM-1.4: every provider carries an explicit model id + version so the
FR-5 provenance block never has to guess what answered a request.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass
class LLMResponse:
    text: str
    model_id: str
    model_version: str
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = "stop"


class LLMProvider(ABC):
    model_id: str
    model_version: str

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.0,
        response_schema: type[BaseModel] | None = None,
    ) -> LLMResponse:
        """`response_schema`, when given, is LLM-3.5's structured-output
        contract: the returned `LLMResponse.text` must be a JSON string
        parseable into that schema (guided generation in production;
        schema-aware templating in the local stub).
        """
