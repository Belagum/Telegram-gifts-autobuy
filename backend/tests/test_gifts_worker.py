# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import backend.services.gifts_service as gs


class _FakeThread:
    def __init__(self, *args, **kwargs):
        self._alive = False

    def start(self):
        self._alive = True

    def is_alive(self):
        return self._alive


def test_start_user_gifts_restarts_dead_worker(monkeypatch):
    monkeypatch.setattr(gs.threading, "Thread", _FakeThread)
    gs.GIFTS_THREADS.pop(999999, None)
    try:
        gs.start_user_gifts(999999)
        first = gs.GIFTS_THREADS[999999].thread

        # поток жив — повторный запуск не пересоздаёт его
        gs.start_user_gifts(999999)
        assert gs.GIFTS_THREADS[999999].thread is first

        # поток умер — запуск создаёт новый
        first._alive = False
        gs.start_user_gifts(999999)
        assert gs.GIFTS_THREADS[999999].thread is not first
    finally:
        gs.GIFTS_THREADS.pop(999999, None)
