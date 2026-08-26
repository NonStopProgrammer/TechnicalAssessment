"""Central, env-driven configuration (LLM-2.3: routing/behavior is config-driven,
not hardcoded). One settings object is imported everywhere instead of each
module reading `os.environ` directly, so every default lives in one place.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_CODE_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "local"

    # Persistence
    database_url: str = "sqlite:///./fincompliance.db"
    redis_url: str = ""

    # Vector store
    qdrant_url: str = ""
    qdrant_local_path: str = "./.qdrant_data"
    qdrant_api_key: str = ""

    # Embeddings / reranking / compression
    embedding_provider: str = "local_hash"
    tei_embedding_url: str = "http://localhost:8081"
    reranker_provider: str = "lexical"
    tei_rerank_url: str = "http://localhost:8082"
    compression_provider: str = "passthrough"

    # LLM orchestration
    llm_router_provider: str = "local_stub"
    llm_generation_provider: str = "local_stub"
    vllm_router_url: str = "http://localhost:8000/v1"
    vllm_generation_url: str = "http://localhost:8001/v1"
    llm_routing_config_path: str = str(_CODE_ROOT / "llm" / "config" / "model_routing.yaml")
    llm_model_registry_path: str = str(_CODE_ROOT / "llm" / "model_registry.yaml")

    # Guardrails
    pii_redaction_provider: str = "regex"
    topical_rail_provider: str = "keyword"
    # RAG-4.6: below this re-ranked top-1 score, treat as "no relevant
    # context" (FR-1.5). Tuned empirically against the lexical/hash MVP
    # providers, whose scores cluster tightly (~0.14-0.20 even for a
    # correct match, see rag/README.md's "known MVP limitations") because
    # bag-of-words scoring can't separate "Tier 1 ratio" from "Capital
    # Conservation Buffer" as cleanly as a real semantic embedding +
    # cross-encoder would. The topical rail (LLM-4.5) is the first line of
    # defense for off-scope queries; this floor is the second, catching an
    # in-scope-sounding question the corpus doesn't actually cover.
    citation_relevance_floor: float = 0.16

    # Auth
    auth_provider: str = "dev_shared_secret"
    jwt_secret: str = "change-me-in-every-real-deployment"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Observability
    langfuse_enabled: bool = False
    langfuse_host: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    log_level: str = "INFO"
    log_format: str = "json"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    api_cors_origins: str = "http://localhost:5173"

    # Agent graph
    agent_checkpointer: str = "memory"
    agent_max_steps: int = 12
    agent_confidence_threshold: float = 0.6

    # MCP
    mcp_transport: str = "stdio"
    mcp_port: int = 8090

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def code_root(self) -> Path:
        return _CODE_ROOT


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — tests can call `get_settings.cache_clear()` to reload."""
    return Settings()
