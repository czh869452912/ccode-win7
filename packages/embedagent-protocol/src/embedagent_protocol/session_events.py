from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Mapping

FRONTEND_FAILURE_CODES = (
    "usage_error",
    "configuration_error",
    "session_not_found",
    "interaction_required",
    "permission_denied",
    "provider_error",
    "runtime_error",
    "cancelled",
    "protocol_error",
)

_SAFE_FAILURE_MESSAGES = {
    "usage_error": "The command arguments are invalid.",
    "configuration_error": "The application configuration is invalid.",
    "provider_error": "The model provider request failed.",
    "provider": "The model provider request failed.",
    "interaction": "The requested interaction could not be completed.",
    "cancelled": "The operation was cancelled.",
    "protocol_error": "The runtime returned an invalid response.",
    "protocol": "The runtime returned an invalid response.",
    "runtime": "The operation failed.",
}


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError("%s must be a string" % field_name)
    normalized = value.strip()
    if not normalized:
        raise ValueError("%s is required" % field_name)
    return normalized


def _positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("%s must be an integer" % field_name)
    if value <= 0:
        raise ValueError("%s must be positive" % field_name)
    return value


@dataclass(frozen=True)
class FailureRecord:
    code: str = "runtime_error"
    message: str = ""
    retryable: bool = False
    source: str = "runtime"
    phase: str = "runtime"
    kind: str = "runtime"
    correlation_id: str = ""
    safe_message: str = ""
    exception_type: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _required_text(self.code, "failure code"))
        if not isinstance(self.message, str):
            raise TypeError("failure message must be a string")
        if not isinstance(self.retryable, bool):
            raise TypeError("failure retryable must be a bool")
        object.__setattr__(self, "source", _required_text(self.source, "failure source"))
        object.__setattr__(self, "phase", _required_text(self.phase, "failure phase"))
        object.__setattr__(self, "kind", _required_text(self.kind, "failure kind"))
        object.__setattr__(self, "correlation_id", str(self.correlation_id or "").strip())
        safe_message = str(self.safe_message or "").strip()
        if not safe_message:
            safe_message = _SAFE_FAILURE_MESSAGES.get(self.kind, "The operation failed.")
        object.__setattr__(self, "safe_message", safe_message)
        object.__setattr__(self, "message", safe_message)
        object.__setattr__(self, "exception_type", str(self.exception_type or "").strip())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "source": self.source,
            "phase": self.phase,
            "kind": self.kind,
            "correlation_id": self.correlation_id,
            "safe_message": self.safe_message,
            "exception_type": self.exception_type,
        }

    @classmethod
    def from_exception(
        cls,
        phase: str,
        kind: str,
        correlation_id: str,
        exception: BaseException,
        code: str = "runtime_error",
        retryable: bool = False,
        source: str = "runtime",
    ) -> "FailureRecord":
        selected_kind = str(kind or "runtime").strip() or "runtime"
        return cls(
            code=code,
            retryable=retryable,
            source=source,
            phase=phase,
            kind=selected_kind,
            correlation_id=correlation_id,
            safe_message=_SAFE_FAILURE_MESSAGES.get(selected_kind, "The operation failed."),
            exception_type=type(exception).__name__,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FailureRecord":
        if not isinstance(value, Mapping):
            raise TypeError("failure record must be a mapping")
        return cls(
            code=value.get("code"),
            message=value.get("message", ""),
            retryable=value.get("retryable", False),
            source=value.get("source", "runtime"),
            phase=value.get("phase", "runtime"),
            kind=value.get("kind", "runtime"),
            correlation_id=value.get("correlation_id", ""),
            safe_message=value.get("safe_message", ""),
            exception_type=value.get("exception_type", ""),
        )


@dataclass(frozen=True)
class SessionEventEnvelope:
    schema_version: int
    event_id: str
    session_id: str
    sequence: int
    event_kind: str
    timestamp: str
    payload: Dict[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            _positive_integer(self.schema_version, "schema_version"),
        )
        object.__setattr__(self, "event_id", _required_text(self.event_id, "event_id"))
        object.__setattr__(self, "session_id", _required_text(self.session_id, "session_id"))
        object.__setattr__(self, "sequence", _positive_integer(self.sequence, "sequence"))
        object.__setattr__(
            self,
            "event_kind",
            _required_text(self.event_kind, "event_kind"),
        )
        object.__setattr__(self, "timestamp", _required_text(self.timestamp, "timestamp"))
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a mapping")
        payload = deepcopy(dict(self.payload))
        json.dumps(payload)
        object.__setattr__(self, "payload", payload)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "session_id": self.session_id,
            "sequence": self.sequence,
            "event_kind": self.event_kind,
            "timestamp": self.timestamp,
            "payload": deepcopy(self.payload),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SessionEventEnvelope":
        if not isinstance(value, Mapping):
            raise TypeError("session event envelope must be a mapping")
        return cls(
            schema_version=value.get("schema_version"),
            event_id=value.get("event_id"),
            session_id=value.get("session_id"),
            sequence=value.get("sequence"),
            event_kind=value.get("event_kind"),
            timestamp=value.get("timestamp"),
            payload=value.get("payload"),
        )
