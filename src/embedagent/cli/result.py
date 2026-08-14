from __future__ import annotations

import sys
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, TextIO

from embedagent_protocol import FailureRecord

_BLOCKED_CODES = frozenset(("interaction_required", "permission_denied"))
_USAGE_CODES = frozenset(("usage_error", "configuration_error"))


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(dict((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return dict((key, _thaw(item)) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    return deepcopy(value)


def exit_code_for_failure(code: str) -> int:
    normalized = str(code or "").strip()
    if normalized in _BLOCKED_CODES:
        return 2
    if normalized in _USAGE_CODES:
        return 3
    if normalized == "cancelled":
        return 130
    return 4


@dataclass(frozen=True)
class CliResult(object):
    session_id: str
    status: str
    exit_code: int
    final_text: str = ""
    outcome: Mapping[str, Any] = field(default_factory=dict)
    failure: Optional[FailureRecord] = None
    schema_version: int = field(default=1, init=False)

    def __post_init__(self) -> None:
        if self.status not in ("completed", "blocked", "failed", "cancelled"):
            raise ValueError("unsupported CLI result status")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise TypeError("exit_code must be an integer")
        if not isinstance(self.outcome, Mapping):
            raise TypeError("outcome must be a mapping")
        if self.failure is not None and not isinstance(self.failure, FailureRecord):
            raise TypeError("failure must be a FailureRecord")
        object.__setattr__(self, "session_id", str(self.session_id or ""))
        object.__setattr__(self, "final_text", str(self.final_text or ""))
        object.__setattr__(self, "outcome", _freeze(deepcopy(dict(self.outcome))))

    @classmethod
    def completed(
        cls,
        session_id: str,
        final_text: str,
        outcome: Optional[Mapping[str, Any]] = None,
    ) -> "CliResult":
        return cls(session_id, "completed", 0, final_text, outcome or {}, None)

    @classmethod
    def blocked(
        cls,
        session_id: str,
        final_text: str = "",
        outcome: Optional[Mapping[str, Any]] = None,
        failure: Optional[FailureRecord] = None,
    ) -> "CliResult":
        return cls(session_id, "blocked", 2, final_text, outcome or {}, failure)

    @classmethod
    def from_failure(cls, session_id: str, failure: FailureRecord) -> "CliResult":
        if not isinstance(failure, FailureRecord):
            raise TypeError("failure must be a FailureRecord")
        exit_code = exit_code_for_failure(failure.code)
        if exit_code == 2:
            status = "blocked"
        elif exit_code == 130:
            status = "cancelled"
        else:
            status = "failed"
        return cls(session_id, status, exit_code, "", {}, failure)

    @classmethod
    def from_runtime_outcome(cls, action: Any) -> "CliResult":
        session_id = ""
        try:
            value = action.to_dict()
            if not isinstance(value, Mapping) or value.get("kind") != "terminal_outcome":
                raise ValueError("runtime outcome must be terminal_outcome")
            session_id = str(value.get("session_id") or "")
            status = str(value.get("status") or "")
            final_text = str(value.get("final_text") or "")
            outcome = value.get("outcome")
            if not isinstance(outcome, Mapping):
                raise TypeError("runtime outcome must contain an outcome mapping")
            failure_value = value.get("failure")
            failure = FailureRecord.from_dict(failure_value) if failure_value is not None else None
            if status == "completed":
                if failure is not None:
                    raise ValueError("completed runtime outcome must not contain a failure")
                return cls.completed(session_id, final_text, outcome)
            if failure is None:
                raise ValueError("non-completed runtime outcome must contain a failure")
            exit_code = exit_code_for_failure(failure.code)
            if exit_code == 2:
                result_status = "blocked"
            elif exit_code == 130:
                result_status = "cancelled"
            else:
                result_status = "failed"
            return cls(
                session_id,
                result_status,
                exit_code,
                final_text,
                outcome,
                failure,
            )
        except (AttributeError, TypeError, ValueError):
            return cls.from_failure(
                session_id,
                FailureRecord(
                    code="protocol_error",
                    message="client runtime returned an invalid terminal outcome",
                    retryable=False,
                    source="cli",
                ),
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "status": self.status,
            "exit_code": self.exit_code,
            "final_text": self.final_text,
            "outcome": _thaw(self.outcome),
            "failure": self.failure.to_dict() if self.failure is not None else None,
        }


def write_failure(failure: FailureRecord, stream: Optional[TextIO] = None) -> int:
    if not isinstance(failure, FailureRecord):
        raise TypeError("failure must be a FailureRecord")
    target = stream if stream is not None else sys.stderr
    target.write("error: %s\n" % failure.code)
    return exit_code_for_failure(failure.code)
