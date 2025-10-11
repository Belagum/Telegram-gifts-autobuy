# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

"""Database unit of work implementation."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import Protocol

from backend.shared.logging import logger
from sqlalchemy.orm import Session


class UnitOfWork(Protocol):
    """Unit of work protocol for transactional operations."""

    def __enter__(self) -> UnitOfWork: ...

    def __exit__(self, exc_type, exc, tb) -> None: ...

    @property
    def session(self) -> Session: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


@dataclass(slots=True)
class SqlAlchemyUnitOfWork(AbstractContextManager, UnitOfWork):
    """SQLAlchemy-backed unit of work."""

    session_factory: Callable[[], Session]

    def __post_init__(self) -> None:
        self._session: Session | None = None

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        self._session = self.session_factory()
        logger.debug("uow: session opened")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self._session is not None
        try:
            if exc:
                logger.warning(f"uow: rollback due to {exc_type}")
                self._session.rollback()
            else:
                self._session.commit()
                logger.debug("uow: committed")
        except Exception:
            logger.exception("uow: exception while finalising")
            self._session.rollback()
            raise
        finally:
            self._session.close()
            logger.debug("uow: session closed")
            self._session = None

    @property
    def session(self) -> Session:
        if self._session is None:
            msg = "UnitOfWork session accessed before entering context"
            raise RuntimeError(msg)
        return self._session

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("UnitOfWork not started")
        self._session.commit()
        logger.debug("uow: manual commit")

    def rollback(self) -> None:
        if self._session is None:
            return
        self._session.rollback()
        logger.debug("uow: manual rollback")


@contextmanager
def unit_of_work_scope(factory: Callable[[], Session]) -> Iterator[Session]:
    """Provide a context manager yielding a session."""

    with SqlAlchemyUnitOfWork(factory) as uow:
        yield uow.session
