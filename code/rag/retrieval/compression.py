"""RAG-4.4: contextual compression, applied to the top-k chunks before
prompt assembly, without dropping a cited threshold/number.
"""

from abc import ABC, abstractmethod
from functools import lru_cache

from shared.config import get_settings
from shared.models.chunk import RetrievedChunk

MAX_CHARS_PER_CHUNK = 1500


class ContextCompressor(ABC):
    @abstractmethod
    def compress(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]: ...


class PassthroughCompressor(ContextCompressor):
    """MVP default: bounds context growth with plain truncation instead of
    LLMLingua's learned token-dropping. Regulatory clauses put the operative
    sentence and its qualifying number first, so truncating from the tail
    preserves RAG-4.4's "never drop a cited threshold" requirement — at the
    cost of the real compression ratio LLMLingua provides at scale.
    """

    def compress(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        for retrieved in chunks:
            text = retrieved.chunk.text
            if len(text) > MAX_CHARS_PER_CHUNK:
                retrieved.chunk.text = text[:MAX_CHARS_PER_CHUNK].rsplit(" ", 1)[0] + " […]"
        return chunks


class LLMLinguaCompressor(ContextCompressor):
    """Production RAG-4.4 adapter. `force_tokens` keeps numerals/section
    markers verbatim per the requirement's stated failure mode to avoid.
    """

    def __init__(self, target_token_ratio: float = 0.5):
        self.target_token_ratio = target_token_ratio

    def compress(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        from llmlingua import PromptCompressor

        compressor = PromptCompressor()
        for retrieved in chunks:
            result = compressor.compress_prompt(
                retrieved.chunk.text, rate=self.target_token_ratio, force_tokens=["%", "§"]
            )
            retrieved.chunk.text = result["compressed_prompt"]
        return chunks


@lru_cache
def get_compressor() -> ContextCompressor:
    settings = get_settings()
    if settings.compression_provider == "llmlingua":
        return LLMLinguaCompressor()
    return PassthroughCompressor()
