from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class _Runner(Generic[T]):  # noqa: UP046
    def __init__(self, coro: Coroutine[Any, Any, T]):
        self.coro = coro
        self.out: T | None = None
        self.err: BaseException | None = None

    def run(self) -> None:
        try:
            self.out = asyncio.run(self.coro)
        except BaseException as e:  # noqa: BLE001
            self.err = e


def run_async(coro: Coroutine[Any, Any, T]) -> T:  # noqa: UP047
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            r: _Runner[T] = _Runner(coro)
            t = threading.Thread(target=r.run, daemon=True)
            t.start()
            t.join()
            if r.err:
                raise r.err
            if r.out is None:
                raise RuntimeError("async operation returned no data")
            return r.out
    except RuntimeError:
        # No running loop
        pass
    return asyncio.run(coro)
