"""Circuit breaker pattern for preventing cascade failures."""

from __future__ import annotations

import time
from typing import Any, Callable, Optional


class CircuitBreakerOpenError(Exception):
    """Raised when a call is attempted while the circuit breaker is OPEN."""

    pass


class CircuitBreaker(object):
    """Standard circuit breaker with CLOSED/OPEN/HALF_OPEN states."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._state = self.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None  # type: Optional[float]

    @property
    def state(self) -> str:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def success_count(self) -> int:
        return self._success_count

    @property
    def last_failure_time(self) -> Optional[float]:
        return self._last_failure_time

    def call(self, func: Callable, *args, **kwargs) -> Any:
        if self._state == self.OPEN:
            if self._last_failure_time is not None:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = self.HALF_OPEN
                    self._success_count = 0
                else:
                    raise CircuitBreakerOpenError(
                        "Circuit breaker is OPEN: service temporarily unavailable"
                    )
            else:
                raise CircuitBreakerOpenError(
                    "Circuit breaker is OPEN: service temporarily unavailable"
                )

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except BaseException:
            self.record_failure()
            raise

    def record_success(self) -> None:
        self._failure_count = 0
        if self._state == self.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.half_open_max_calls:
                self._state = self.CLOSED
                self._success_count = 0

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._state == self.HALF_OPEN:
            self._state = self.OPEN
        elif self._failure_count >= self.failure_threshold:
            self._state = self.OPEN

    def reset(self) -> None:
        self._state = self.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
