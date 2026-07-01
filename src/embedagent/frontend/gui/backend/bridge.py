from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass(frozen=True)
class DispatchResult(object):
    queued: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return bool(self.queued)


class ThreadsafeAsyncDispatcher(object):
    """Schedules coroutines onto the FastAPI event loop from worker threads."""

    def __init__(self) -> None:
        self._loop = None  # type: Optional[asyncio.AbstractEventLoop]
        self._lock = threading.RLock()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        with self._lock:
            self._loop = loop

    def bind_running_loop(self) -> None:
        self.set_loop(asyncio.get_running_loop())

    def dispatch(self, coroutine_factory: Callable[[], Awaitable[Any]]) -> DispatchResult:
        with self._lock:
            loop = self._loop
        if loop is None:
            return DispatchResult(False, "loop_missing")
        if loop.is_closed():
            return DispatchResult(False, "loop_closed")

        def runner() -> None:
            asyncio.create_task(coroutine_factory())

        loop.call_soon_threadsafe(runner)
        return DispatchResult(True, "")
