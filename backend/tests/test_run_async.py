# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import asyncio

import pytest

from backend.shared.utils.asyncio_utils import run_async


async def _returns_none():
    return None


async def _returns_value():
    return 42


async def _raises_runtime():
    raise RuntimeError("boom")


def test_run_async_returns_value_no_loop():
    assert run_async(_returns_value()) == 42


def test_run_async_allows_none_in_running_loop():
    # внутри asyncio.run уже крутится цикл -> потоковая ветка run_async;
    # раньше None ошибочно превращался в RuntimeError("no data")
    async def outer():
        return run_async(_returns_none())

    assert asyncio.run(outer()) is None


def test_run_async_propagates_error_in_running_loop():
    # ошибка из корутины должна пробрасываться, а не глотаться except RuntimeError
    async def outer():
        return run_async(_raises_runtime())

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(outer())
