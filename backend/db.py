# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker

from .logger import logger

ENGINE = create_engine(
    "sqlite:///app.db",
    echo=False,
    future=True,
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True,
)

@event.listens_for(ENGINE, "connect")
def _set_sqlite_pragmas(dbapi_conn, _):
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

class Base(DeclarativeBase):
    pass

SessionLocal = scoped_session(
    sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, expire_on_commit=False)
)

def get_db():
    db = SessionLocal()
    logger.debug("DB session opened")
    try:
        yield db
    except Exception:
        logger.exception("DB session error; rolling back")
        db.rollback()
        raise
    finally:
        try:
            db.close()
            logger.debug("DB session closed")
        finally:
            SessionLocal.remove()

def init_db():
    Base.metadata.create_all(bind=ENGINE)
    logger.info("Database schema ensured")
