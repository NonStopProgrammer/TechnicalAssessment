"""FastAPI application entrypoint.

    uvicorn backend.main:api --host 0.0.0.0 --port 8080

(from the `code/` directory, with PYTHONPATH=. — see backend/README.md).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v1.router import api_router
from backend.core.errors import register_exception_handlers
from shared.config import get_settings
from shared.db.base import init_db
from shared.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    _seed_demo_data_if_empty()
    logger.info("backend.startup", environment=get_settings().environment)
    yield
    logger.info("backend.shutdown")


def _seed_demo_data_if_empty() -> None:
    """Best-effort convenience so `uvicorn backend.main:api` alone is
    enough to demo FR-1/FR-2 — never blocks startup on failure, since a
    corpus/seed issue shouldn't take the whole API down (see rag/RAG-7).
    """
    try:
        from pathlib import Path

        from agentic.tools.get_transaction_details import seed_transactions
        from rag.ingestion.pipeline import ingest_directory
        from shared.config import get_settings

        corpus_dir = get_settings().code_root / "rag" / "corpus" / "sample_documents"
        if corpus_dir.exists():
            ingest_directory(corpus_dir)  # RAG-1.4: idempotent, safe to call every startup
        seed_transactions()
    except Exception as exc:  # noqa: BLE001
        logger.warning("backend.startup_seed_failed", error=str(exc))


settings = get_settings()
api = FastAPI(
    title="FinServ AI Regulatory Compliance Assistant",
    description="MVP slice of the architecture in requirements/ — FR-1..FR-4 over RAG + LLM orchestration + the agentic compliance checker.",
    version="0.1.0-mvp",
    lifespan=lifespan,
)

api.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(api)
api.include_router(api_router, prefix="/api/v1")
