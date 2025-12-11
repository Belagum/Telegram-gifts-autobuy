# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

import asyncio
import concurrent.futures
import os
import sqlite3
import threading
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, TypeVar

from pyrogram import Client
from pyrogram.errors import AuthKeyUnregistered, Unauthorized

from ..shared.logging import logger
from .session_locks_service import session_lock_for

_START_ATTEMPTS = 4
_START_TIMEOUT = 20.0
_DBLOCK_MAX_BACKOFF = 2.0


class _Box:
    __slots__ = (
        "path",
        "api_id",
        "api_hash",
        "client",
        "loop",
        "init_lock",
        "call_lock",
        "last_call",
    )

    def __init__(self, path: str, api_id: int, api_hash: str):
        self.path = os.path.abspath(path)
        self.api_id = api_id
        self.api_hash = api_hash
        self.client: Client | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.init_lock = threading.Lock()
        self.call_lock: asyncio.Lock | None = None
        self.last_call = 0.0


_CLIENTS: dict[str, _Box] = {}
_CLIENTS_GUARD = threading.Lock()

_IO_LOOP: asyncio.AbstractEventLoop | None = None
_IO_THREAD: threading.Thread | None = None
_IO_LOCK = threading.Lock()


def _ensure_io_loop() -> asyncio.AbstractEventLoop:
    global _IO_LOOP, _IO_THREAD
    with _IO_LOCK:
        if (
            _IO_LOOP
            and not _IO_LOOP.is_closed()
            and _IO_THREAD
            and _IO_THREAD.is_alive()
        ):
            logger.debug(f"tg_clients: reuse io loop thread={_IO_THREAD.name}")
            return _IO_LOOP
        loop = asyncio.new_event_loop()

        def _runner() -> None:
            asyncio.set_event_loop(loop)
            logger.debug(
                f"tg_clients: io loop running thread={threading.current_thread().name}"
            )
            try:
                loop.run_forever()
            finally:
                logger.debug(
                    f"tg_clients: io loop stopped thread={threading.current_thread().name}"
                )

        t = threading.Thread(target=_runner, name="tg-io", daemon=True)
        _IO_LOOP, _IO_THREAD = loop, t
        t.start()
        logger.info(f"tg_clients: started io loop thread={t.name}")
        return loop


def _loop_alive(loop: asyncio.AbstractEventLoop | None) -> bool:
    return bool(loop and not loop.is_closed())


T = TypeVar("T")


def _run_in_loop(  # noqa: UP047
    loop: asyncio.AbstractEventLoop, coro: Coroutine[Any, Any, T]
) -> Awaitable[T]:
    fut: concurrent.futures.Future[T] = asyncio.run_coroutine_threadsafe(coro, loop)
    return asyncio.wrap_future(fut)


def _ensure_session_directory(path: str) -> None:
    try:
        session_dir = os.path.dirname(os.path.abspath(path))
        if session_dir:
            os.makedirs(session_dir, exist_ok=True)
            logger.debug(
                f"tg_clients: ensured session directory exists path={session_dir}"
            )
    except OSError as e:
        logger.exception(
            f"tg_clients: failed to create session directory path={path} error={type(e).__name__}"
        )
        raise


async def _ensure_started(path: str, api_id: int, api_hash: str) -> _Box:
    key = os.path.abspath(path)
    logger.debug(f"tg_clients: ensure_started path={key}")
    with _CLIENTS_GUARD:
        box = _CLIENTS.get(key)
        if not box:
            box = _Box(key, api_id, api_hash)
            _CLIENTS[key] = box
            logger.debug(
                f"tg_clients: created client box path={box.path} api_id={box.api_id}"
            )
    if (
        box.client
        and getattr(box.client, "is_connected", False)
        and _loop_alive(box.loop)
    ):
        logger.debug(f"tg_clients: reuse active client path={box.path}")
        return box
    with box.init_lock:
        if (
            box.client
            and getattr(box.client, "is_connected", False)
            and _loop_alive(box.loop)
        ):
            logger.debug(f"tg_clients: reuse active client after lock path={box.path}")
            return box
        io = _ensure_io_loop()
        box.loop = io

        async def _start_once() -> None:
            logger.debug(f"tg_clients: starting pyrogram client path={box.path}")
            _ensure_session_directory(box.path)
            c = Client(
                box.path, api_id=box.api_id, api_hash=box.api_hash, no_updates=True
            )
            try:
                await asyncio.wait_for(c.connect(), timeout=_START_TIMEOUT)
                logger.debug(f"tg_clients: client connected path={box.path}")

                await asyncio.wait_for(c.initialize(), timeout=_START_TIMEOUT)
                logger.debug(f"tg_clients: client initialized path={box.path}")

                try:
                    await asyncio.wait_for(c.get_me(), timeout=5.0)
                    logger.debug(f"tg_clients: session authorized path={box.path}")
                except (AuthKeyUnregistered, Unauthorized) as e:
                    logger.warning(
                        f"tg_clients: session not authorized path={box.path} "
                        f"error={type(e).__name__}"
                    )
                    try:
                        await c.terminate()
                    except Exception:
                        pass
                    raise AuthKeyUnregistered("Session is not authorized") from e
            except TimeoutError as e:
                logger.warning(
                    f"tg_clients: pyrogram init timeout path={box.path} timeout={_START_TIMEOUT}"
                )
                try:
                    await c.terminate()
                except Exception:
                    logger.debug(
                        f"tg_clients: terminate after timeout failed path={box.path}"
                    )
                raise RuntimeError("pyrogram.initialize timeout") from e
            box.client = c
            box.call_lock = asyncio.Lock()
            logger.info(f"tg_clients: pyrogram client ready path={box.path}")

        async def _start_with_retries() -> None:
            backoff = 0.2
            last_err: BaseException | None = None
            for attempt in range(1, _START_ATTEMPTS + 1):
                logger.info(
                    f"tg_clients: start attempt path={box.path} attempt={attempt}"
                )
                try:
                    await _start_once()
                    logger.info(
                        f"tg_clients: start success path={box.path} attempt={attempt}"
                    )
                    return
                except sqlite3.OperationalError as e:
                    last_err = e
                    message = str(e)
                    logger.warning(
                        f"tg_clients: sqlite error path={box.path} attempt={attempt} "
                        f"error={type(e).__name__} msg={message}"
                    )
                    if "database is locked" in message.lower():
                        logger.debug(
                            f"tg_clients: sqlite locked path={box.path} attempt={attempt} "
                            f"backoff={backoff}"
                        )
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, _DBLOCK_MAX_BACKOFF)
                        continue
                    break
                except AuthKeyUnregistered as e:
                    logger.warning(
                        f"tg_clients: session invalid (AuthKeyUnregistered) path={box.path} "
                        f"attempt={attempt} - stopping retries"
                    )
                    raise e
                except Exception as e:
                    last_err = e
                    logger.exception(
                        f"tg_clients: start attempt failed path={box.path} attempt={attempt}"
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, _DBLOCK_MAX_BACKOFF)
            logger.error(
                f"tg_clients: unable to start client path={box.path} attempts={_START_ATTEMPTS}"
            )
            raise last_err or RuntimeError("pyrogram.start failed")

        logger.debug(f"tg_clients: acquiring session lock path={key}")
        try:
            with session_lock_for(key):
                logger.debug(f"tg_clients: acquired session lock path={key}")
                await _run_in_loop(io, _start_with_retries())
        finally:
            logger.debug(f"tg_clients: released session lock path={key}")
        logger.debug(f"tg_clients: ensure_started ready path={box.path}")
        return box


async def tg_call(
    path: str,
    api_id: int,
    api_hash: str,
    op: Callable[[Client], Awaitable[Any]],
    min_interval: float = 0.0,
    op_timeout: float | None = None,
):
    op_name = (
        getattr(op, "__qualname__", None)
        or getattr(op, "__name__", None)
        or op.__class__.__name__
    )
    logger.debug(
        f"tg_clients: call start path={os.path.abspath(path)} op={op_name} "
        f"min_interval={min_interval} timeout={op_timeout}"
    )
    box = await _ensure_started(path, api_id, api_hash)
    if (
        not _loop_alive(box.loop)
        or not box.client
        or not getattr(box.client, "is_connected", False)
    ):
        logger.warning(
            f"tg_clients: client unhealthy path={box.path} op={op_name}, restarting"
        )
        box = await _ensure_started(path, api_id, api_hash)

    async def inner() -> Any:
        if box.call_lock is None or box.client is None:
            logger.error(
                f"tg_clients: call aborted path={box.path} op={op_name}, client not initialized"
            )
            raise RuntimeError("telegram client is not initialized")
        async with box.call_lock:
            if min_interval > 0:
                now = asyncio.get_running_loop().time()
                delay = max(0.0, box.last_call + min_interval - now)
                if delay > 0:
                    logger.debug(
                        f"tg_clients: throttling path={box.path} op={op_name} delay={delay:.3f}s"
                    )
                    await asyncio.sleep(delay)
            coro = op(box.client)
            awaited = asyncio.wait_for(coro, timeout=op_timeout) if op_timeout else coro
            try:
                result = await awaited
            except Exception:
                logger.exception(
                    f"tg_clients: call failed path={box.path} op={op_name}"
                )
                raise
            box.last_call = asyncio.get_running_loop().time()
            logger.debug(f"tg_clients: call success path={box.path} op={op_name}")
            return result

    try:
        cur = asyncio.get_running_loop()
    except RuntimeError:
        cur = None
        logger.debug(f"tg_clients: no running loop path={box.path} op={op_name}")

    if cur is box.loop:
        logger.debug(f"tg_clients: executing directly path={box.path} op={op_name}")
        return await inner()
    if not _loop_alive(box.loop):
        logger.warning(
            f"tg_clients: loop not alive path={box.path} op={op_name}, restarting"
        )
        box = await _ensure_started(path, api_id, api_hash)
    if box.loop is None:
        logger.error(f"tg_clients: loop missing path={box.path} op={op_name}")
        raise RuntimeError("telegram client loop is not initialized")
    logger.debug(f"tg_clients: scheduling on loop path={box.path} op={op_name}")
    return await _run_in_loop(box.loop, inner())


async def tg_stop(path: str) -> None:
    key = os.path.abspath(path)
    logger.info(f"tg_clients: stop requested path={key}")
    with _CLIENTS_GUARD:
        box = _CLIENTS.get(key)
    if not box:
        logger.debug(f"tg_clients: stop skipped no client path={key}")
        return
    loop = box.loop
    if not _loop_alive(loop) or not box.client:
        logger.debug(f"tg_clients: client already inactive path={key}")
        with _CLIENTS_GUARD:
            _CLIENTS.pop(key, None)
        logger.debug(f"tg_clients: removed inactive client path={key}")
        return
    if loop is None:
        logger.error(f"tg_clients: stop aborted no loop path={key}")
        return

    async def stopper() -> None:
        if box.call_lock is None or box.client is None:
            logger.debug(f"tg_clients: stopper skipped path={key}")
            return
        async with box.call_lock:
            logger.info(f"tg_clients: stopping client path={key}")
            try:
                await asyncio.wait_for(box.client.stop(), timeout=5.0)
                logger.info(f"tg_clients: client stop completed path={key}")
            except Exception:
                logger.exception(f"tg_clients: stop failed path={key}")

    try:
        await _run_in_loop(loop, stopper())
    except Exception:
        logger.exception(f"tg_clients: stop scheduling failed path={key}")
    finally:
        with _CLIENTS_GUARD:
            _CLIENTS.pop(key, None)
        logger.debug(f"tg_clients: stop cleanup done path={key}")


async def tg_shutdown(paths: set[str]) -> None:
    logger.info(f"tg_clients: shutdown requested count={len(paths)}")
    for p in set(paths):
        try:
            await tg_stop(p)
            logger.debug(f"tg_clients: shutdown completed path={os.path.abspath(p)}")
        except Exception:
            logger.exception(f"tg_clients: shutdown failed path={os.path.abspath(p)}")
