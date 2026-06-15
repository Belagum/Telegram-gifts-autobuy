# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, Generic, TypeVar, cast

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
    # Определение запущенного цикла отделено от обработки результата: иначе
    # RuntimeError из самой корутины ловился бы этим except, и None был бы
    # ошибочно принят за «нет результата».
    try:
        loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        r: _Runner[T] = _Runner(coro)
        t = threading.Thread(target=r.run, daemon=True)
        t.start()
        t.join()
        if r.err:
            raise r.err
        return cast("T", r.out)

    return asyncio.run(coro)
