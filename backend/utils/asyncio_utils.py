from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            out: T | None = None
            err: BaseException | None = None

            def _runner() -> None:
                nonlocal out, err
                try:
                    out = asyncio.run(coro)
                except BaseException as e:  # noqa: BLE001
                    err = e

            t = threading.Thread(target=_runner, daemon=True)
            t.start()
            t.join()
            if err:
                raise err
            if out is None:
                raise RuntimeError("async operation returned no data")
            return out
    except RuntimeError:
        # No running loop
        pass
    return asyncio.run(coro)
