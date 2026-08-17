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
                retryable=False,
                source="session",
                phase="session_lookup",
                kind="runtime",
                safe_message="Session was not found.",
            )
        )


def failure_for_exception(error: BaseException, source: str) -> FailureRecord:
    if isinstance(error, FrontendPortError):
        return error.failure
    if isinstance(error, ModelClientError):
        return FailureRecord.from_exception(
            phase="provider_request",
            kind="provider",
            correlation_id="",
            exception=error,
            code="provider_error",
            retryable=True,
            source="provider",
        )
    if isinstance(error, (AsyncCancelledError, FutureCancelledError)):
        return FailureRecord.from_exception(
            phase="runtime",
            kind="cancelled",
            correlation_id="",
            exception=error,
            code="cancelled",
            retryable=False,
            source=source,
        )
    if isinstance(error, (TypeError, ValueError)):
        return FailureRecord.from_exception(
            phase="protocol",
            kind="protocol",
            correlation_id="",
            exception=error,
            code="protocol_error",
            retryable=False,
            source=source,
        )
    return FailureRecord.from_exception(
        phase="runtime",
        kind="runtime",
        correlation_id="",
        exception=error,
        code="runtime_error",
        retryable=False,
        source=source,
    )
