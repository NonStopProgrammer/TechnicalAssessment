"""Engine/session setup. SQLite by default (zero-infra local dev/tests, see
ENVIRONMENT=local in .env.example); docker-compose points DATABASE_URL at
Postgres (RDS in production, per requirements/06-infrastructure-nfr-
requirements.md INFRA-1.6) without any code change.
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from shared.config import get_settings


class Base(DeclarativeBase):
    pass


def _build_engine():
    settings = get_settings()
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, connect_args=connect_args, future=True)


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Creates tables if missing. MVP stand-in for Alembic migrations —
    `alembic/` would own this in a real deployment (see backend/README).
    """
    from shared.db import models  # noqa: F401 — registers tables on Base.metadata

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """For use outside request handlers (ingestion pipeline, scripts, tests)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
