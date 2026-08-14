from __future__ import annotations

from asyncio import CancelledError as AsyncCancelledError
from concurrent.futures import CancelledError as FutureCancelledError

from embedagent_core.model import ModelClientError
from embedagent_protocol import FailureRecord


class FrontendPortError(RuntimeError):
    def __init__(self, failure: FailureRecord) -> None:
        super().__init__(failure.message)
        self.failure = failure


class SessionNotFoundError(FrontendPortError, ValueError):
    def __init__(self, reference: str) -> None:
        super().__init__(
            FailureRecord(
                code="session_not_found",
                message="Session was not found: %s" % str(reference or ""),
                retryable=False,
                source="session",
            )
        )


def failure_for_exception(error: BaseException, source: str) -> FailureRecord:
    if isinstance(error, FrontendPortError):
        return error.failure
    if isinstance(error, ModelClientError):
        return FailureRecord(
            code="provider_error",
            message=str(error),
            retryable=True,
            source="provider",
        )
    if isinstance(error, (AsyncCancelledError, FutureCancelledError)):
        return FailureRecord(
            code="cancelled",
            message=str(error),
            retryable=False,
            source=source,
        )
    if isinstance(error, (TypeError, ValueError)):
        return FailureRecord(
            code="protocol_error",
            message=str(error),
            retryable=False,
            source=source,
        )
    return FailureRecord(
        code="runtime_error",
        message=str(error),
        retryable=False,
        source=source,
    )
