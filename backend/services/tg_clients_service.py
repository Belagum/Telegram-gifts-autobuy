# SPDX-License-Identifier: Apache-2.0
# Copyright 2025

import asyncio, threading, time, os, sqlite3
from typing import Dict, Optional, Callable, Awaitable, Set
from pyrogram import Client
from .session_locks_service import session_lock_for

class _Box:
    __slots__ = ("path","api_id","api_hash","client","loop","init_lock","call_lock","last_call")
    def __init__(self, path:str, api_id:int, api_hash:str):
        self.path = os.path.abspath(path); self.api_id = api_id; self.api_hash = api_hash
        self.client: Optional[Client] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.init_lock = threading.Lock()
        self.call_lock: Optional[asyncio.Lock] = None
        self.last_call = 0.0

_CLIENTS: Dict[str, _Box] = {}
_CLIENTS_GUARD = threading.Lock()

async def _ensure_started(path:str, api_id:int, api_hash:str) -> _Box:
    key = os.path.abspath(path)
    with _CLIENTS_GUARD:
        box = _CLIENTS.get(key)
        if not box:
            box = _Box(key, api_id, api_hash); _CLIENTS[key] = box
    if box.client and getattr(box.client, "is_connected", False): return box
    with box.init_lock:
        if box.client and getattr(box.client, "is_connected", False): return box
        box.loop = asyncio.get_running_loop()
        backoff = 0.2
        with session_lock_for(key):
            for _ in range(6):
                try:
                    c = Client(box.path, api_id=box.api_id, api_hash=box.api_hash, no_updates=True)
                    await c.start()
                    box.client = c
                    box.call_lock = asyncio.Lock()
                    return box
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e).lower() and backoff <= 2.0:
                        await asyncio.sleep(backoff); backoff = min(backoff*2, 2.0); continue
                    raise
    return box  # pragma: no cover

async def tg_call(path:str, api_id:int, api_hash:str, op:Callable[[Client], Awaitable], min_interval:float=0.0):
    box = await _ensure_started(path, api_id, api_hash)
    async def inner():
        async with box.call_lock:  # type: ignore[arg-type]
            if min_interval>0:
                now = asyncio.get_running_loop().time()
                delay = max(0.0, box.last_call + min_interval - now)
                if delay>0: await asyncio.sleep(delay)
            res = await op(box.client)  # type: ignore[arg-type]
            box.last_call = asyncio.get_running_loop().time()
            return res
    cur = asyncio.get_running_loop()
    if box.loop is cur:
        return await inner()
    fut = asyncio.run_coroutine_threadsafe(inner(), box.loop)  # type: ignore[arg-type]
    return await asyncio.wrap_future(fut)

async def tg_stop(path:str) -> None:
    key = os.path.abspath(path)
    with _CLIENTS_GUARD:
        box = _CLIENTS.get(key)
    if not box or not box.client or not box.loop: return
    async def stopper():
        async with box.call_lock:  # type: ignore[arg-type]
            await box.client.stop()  # type: ignore[union-attr]
    fut = asyncio.run_coroutine_threadsafe(stopper(), box.loop)
    try:
        await asyncio.wrap_future(fut)
    finally:
        with _CLIENTS_GUARD:
            _CLIENTS.pop(key, None)

async def tg_shutdown(paths:Set[str]) -> None:
    for p in set(paths):
        try: await tg_stop(p)
        except Exception: pass
