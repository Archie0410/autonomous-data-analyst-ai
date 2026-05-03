"""
SQLAlchemy engine + session factory.

The same engine is shared between:
  - the system metadata tables (datasets, chat_messages, query_logs)
  - the dynamically-created user data tables (one per uploaded CSV)
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.db_models import Base
from app.utils.logger import logger

_engine: Engine = create_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)

SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create system metadata tables on startup."""
    logger.info("Initializing database at {}", settings.database_url)
    Base.metadata.create_all(bind=_engine)


def get_engine() -> Engine:
    return _engine


def get_session() -> Session:
    """FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Standalone context-managed session for non-FastAPI callers (agent, services)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
