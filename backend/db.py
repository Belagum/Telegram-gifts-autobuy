# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""Database layer helpers and session utilities."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker

from backend.config import load_config
from backend.logger import logger

_config = load_config()


class Base(DeclarativeBase):
    """Declarative base for ORM models."""


connect_args: dict[str, object] = {}
if _config.database.url.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False,
        "timeout": int(_config.database.pool_timeout),
    }

ENGINE: Engine = create_engine(
    _config.database.url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_size=_config.database.pool_size,
    max_overflow=_config.database.max_overflow,
    pool_timeout=_config.database.pool_timeout,
    connect_args=connect_args,
)


@event.listens_for(ENGINE, "connect")
def _set_sqlite_pragmas(dbapi_conn, _):
    """Apply safety PRAGMAs when using SQLite."""

    if not _config.database.url.startswith("sqlite"):
        return
    cur = dbapi_conn.cursor()
    try:
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA foreign_keys=ON;")
        cur.execute("PRAGMA busy_timeout=30000;")
    except Exception:
        logger.exception("Failed to apply SQLite PRAGMAs")
    finally:
        cur.close()


SessionLocal = scoped_session(
    sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, expire_on_commit=False)
)


@contextmanager
def session_scope() -> Iterator:
    """Provide a transactional scope for imperative consumers."""

    session = SessionLocal()
    logger.debug("db.session: opened scoped session")
    try:
        yield session
        session.commit()
        logger.debug("db.session: committed scoped session")
    except Exception:
        logger.exception("db.session: error, rolling back")
        session.rollback()
        raise
    finally:
        session.close()
        SessionLocal.remove()
        logger.debug("db.session: closed scoped session")


def get_db():
    """Yield DB session for FastAPI/Flask dependency injection."""

    with session_scope() as session:
        yield session


def init_db() -> None:
    """Ensure database schema exists."""

    Base.metadata.create_all(bind=ENGINE)
    logger.info("Database schema ensured")
