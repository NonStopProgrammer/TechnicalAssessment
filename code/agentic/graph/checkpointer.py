"""AGENT-2.2: LangGraph's checkpointer persists state at every node
transition — this *is* the audit trail for SEC-2.3/the Internal Auditor
persona, so a checkpointer is always wired, just backed by a different
store depending on environment (AGENT_CHECKPOINTER in .env).
"""

from functools import lru_cache

from shared.config import get_settings


@lru_cache
def get_checkpointer():
    settings = get_settings()
    if settings.agent_checkpointer == "postgres":
        # Production (requirements-full.txt: langgraph-checkpoint-postgres).
        # `from_conn_string` is a context manager in LangGraph's API; kept
        # open for the process lifetime here rather than per-request, same
        # lifecycle as shared.db.base's SQLAlchemy engine.
        from langgraph.checkpoint.postgres import PostgresSaver

        saver_cm = PostgresSaver.from_conn_string(settings.database_url)
        saver = saver_cm.__enter__()
        saver.setup()
        return saver

    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()
