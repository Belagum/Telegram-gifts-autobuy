# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Vova Orig

import asyncio
import threading
from typing import Any, Coroutine

from backend.infrastructure.telegram_auth.exceptions import EventLoopError, TelegramAuthError
from backend.shared.logging import logger


class EventLoopManager:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._thread: threading.Thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="TelegramAuthEventLoop"
        )
        self._started = False
        
        logger.debug(f"EventLoopManager: creating thread name={self._thread.name}")
        self._thread.start()
        self._started = True
        logger.debug(f"EventLoopManager: thread started name={self._thread.name}")

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        thread_name = threading.current_thread().name
        logger.debug(f"EventLoopManager: loop runner start thread={thread_name}")
        
        try:
            self._loop.run_forever()
        except Exception:
            logger.exception(f"EventLoopManager: loop error thread={thread_name}")
        finally:
            logger.debug(f"EventLoopManager: loop runner stop thread={thread_name}")

    def run(self, coro: Coroutine[Any, Any, Any]) -> Any:
        if not self._started:
            raise EventLoopError("Event loop not started", error_code="loop_not_started")
        
        logger.debug(f"EventLoopManager: scheduling coroutine thread={self._thread.name}")
        
        try:
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            return future.result()
        except TelegramAuthError:
            raise
        except Exception as e:
            logger.exception(f"EventLoopManager: execution failed thread={self._thread.name}")
            raise EventLoopError(
                f"Failed to execute coroutine: {e}",
                error_code="execution_failed"
            ) from e

    def stop(self) -> None:
        if not self._started:
            logger.debug("EventLoopManager: already stopped")
            return
        
        logger.debug(f"EventLoopManager: stopping thread={self._thread.name}")
        
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=2.0)
            self._started = False
            logger.debug(f"EventLoopManager: stopped thread={self._thread.name}")
        except Exception:
            logger.exception(f"EventLoopManager: stop failed thread={self._thread.name}")

    def __del__(self) -> None:
        try:
            self.stop()
        except Exception:
            pass

