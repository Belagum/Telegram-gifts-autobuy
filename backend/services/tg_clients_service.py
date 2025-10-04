# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova orig

import asyncio
import os
import sqlite3
import threading
from collections.abc import Awaitable, Callable
from typing import Any

from pyrogram import Client

from .session_locks_service import session_lock_for

_START_ATTEMPTS = 4
_START_TIMEOUT = 20.0
_DBLOCK_MAX_BACKOFF = 2.0

class _Box:
    __slots__ = ("path","api_id","api_hash","client","loop","init_lock","call_lock","last_call")
    def __init__(self, path:str, api_id:int, api_hash:str):
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
        if _IO_LOOP and not _IO_LOOP.is_closed() and _IO_THREAD and _IO_THREAD.is_alive():
            return _IO_LOOP
        loop = asyncio.new_event_loop()
        def _runner(): asyncio.set_event_loop(loop) 
        loop.run_forever()
        t = threading.Thread(target=_runner, name="tg-io", daemon=True) 
        t.start()
        _IO_LOOP, _IO_THREAD = loop, t
        return loop

def _loop_alive(loop: asyncio.AbstractEventLoop | None) -> bool:
    return bool(loop and not loop.is_closed())

def _run_in_loop(loop: asyncio.AbstractEventLoop, coro: Awaitable[Any]) -> Awaitable[Any]:
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    return asyncio.wrap_future(fut)

async def _ensure_started(path:str, api_id:int, api_hash:str) -> _Box:
    key = os.path.abspath(path)
    with _CLIENTS_GUARD:
        box = _CLIENTS.get(key)
        if not box:
            box = _Box(key, api_id, api_hash) 
            _CLIENTS[key] = box
    if box.client and getattr(box.client, "is_connected", False) and _loop_alive(box.loop):
        return box
    with box.init_lock:
        if box.client and getattr(box.client, "is_connected", False) and _loop_alive(box.loop):
            return box
        io = _ensure_io_loop()
        box.loop = io

        async def _start_once():
            c = Client(box.path, api_id=box.api_id, api_hash=box.api_hash, no_updates=True)
            try:
                await asyncio.wait_for(c.start(), timeout=_START_TIMEOUT)
            except TimeoutError as e:
                try:
                    await c.stop()
                except Exception:
                    pass
                raise RuntimeError("pyrogram.start timeout") from e
            box.client = c
            box.call_lock = asyncio.Lock()

        async def _start_with_retries():
            backoff = 0.2
            last_err: BaseException | None = None
            for _ in range(_START_ATTEMPTS):
                try:
                    await _start_once() 
                    return
                except sqlite3.OperationalError as e:
                    last_err = e
                    if "database is locked" in str(e).lower():
                        await asyncio.sleep(backoff)
                        backoff = min(backoff*2, _DBLOCK_MAX_BACKOFF)
                        continue
                    break
                except Exception as e:
                    last_err = e
                    await asyncio.sleep(backoff) 
                    backoff = min(backoff*2, _DBLOCK_MAX_BACKOFF)
            raise last_err or RuntimeError("pyrogram.start failed")

        # берём файловый лок в текущем потоке, а не внутри ид треда
        with session_lock_for(key):
            await _run_in_loop(io, _start_with_retries())
        return box

async def tg_call(path:str, api_id:int, api_hash:str, op:Callable[[Client], Awaitable[Any]], min_interval:float=0.0, op_timeout: float | None=None):
    box = await _ensure_started(path, api_id, api_hash)
    if not _loop_alive(box.loop) or not box.client or not getattr(box.client, "is_connected", False):
        box = await _ensure_started(path, api_id, api_hash)

    async def inner():
        async with box.call_lock:  # type: ignore[arg-type]
            if min_interval>0:
                now = asyncio.get_running_loop().time()
                delay = max(0.0, box.last_call + min_interval - now)
                if delay > 0:
                    await asyncio.sleep(delay)
            coro = op(box.client)  # type: ignore[arg-type]
            res = await (asyncio.wait_for(coro, timeout=op_timeout) if op_timeout else coro)
            box.last_call = asyncio.get_running_loop().time()
            return res

    try:
        cur = asyncio.get_running_loop()
    except RuntimeError:
        cur = None

    if cur is box.loop:
        return await inner()
    if not _loop_alive(box.loop):
        box = await _ensure_started(path, api_id, api_hash)
    return await _run_in_loop(box.loop, inner())  # type: ignore[arg-type]

async def tg_stop(path: str) -> None:
    key = os.path.abspath(path)
    with _CLIENTS_GUARD:
        box = _CLIENTS.get(key)
    if not box:
        return
    loop = box.loop
    if not _loop_alive(loop) or not box.client:
        with _CLIENTS_GUARD:
            _CLIENTS.pop(key, None)
        return

    async def stopper():
        async with box.call_lock:  # type: ignore[arg-type]
            try:
                await asyncio.wait_for(box.client.stop(), timeout=5.0)  # type: ignore[union-attr]
            except Exception:
                pass

    try:
        await _run_in_loop(loop, stopper())  # type: ignore[arg-type]
    finally:
        with _CLIENTS_GUARD:
            _CLIENTS.pop(key, None)


async def tg_shutdown(paths:set[str]) -> None:
    for p in set(paths):
        try:
            await tg_stop(p)
        except Exception:
            pass
