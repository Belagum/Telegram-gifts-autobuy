# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

from typing import Any, Coroutine, Protocol


class IEventLoop(Protocol):
    def run(self, coro: Coroutine[Any, Any, Any]) -> Any: ...

    def stop(self) -> None: ...

