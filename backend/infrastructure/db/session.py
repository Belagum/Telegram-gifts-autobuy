# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker

from backend.shared.config import load_config
from backend.shared.logging import logger

_config = load_config()


class Base(DeclarativeBase):
    pass


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


SessionLocal = scoped_session(
    sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, expire_on_commit=False)
)


@contextmanager
def session_scope() -> Iterator:
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
    with session_scope() as session:
        yield session


def init_db() -> None:
    Base.metadata.create_all(bind=ENGINE)
    logger.info("Database schema ensured")
