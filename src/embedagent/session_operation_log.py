from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

_STARTED = "started"
_FINISHED = "finished"
_INTERRUPTED = "interrupted"


@dataclass
class OperationRecord(object):
    operation_id: str
    kind: str
    status: str = _STARTED
    turn_id: str = ""
    step_id: str = ""
    tool_call_id: str = ""
    parent_operation_id: str = ""
    started_at: str = ""
    finished_at: str = ""
    interrupted_reason: str = ""
    retryable: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationLogState(object):
    operations: Dict[str, OperationRecord] = field(default_factory=dict)
    order: List[str] = field(default_factory=list)

    @property
    def interrupted_count(self) -> int:
        return sum(1 for item in self.operations.values() if item.status == _INTERRUPTED)

    @property
    def started_count(self) -> int:
        return sum(1 for item in self.operations.values() if item.status == _STARTED)

    @property
    def finished_count(self) -> int:
        return sum(1 for item in self.operations.values() if item.status == _FINISHED)


class OperationLogReducer(object):
    """Reduce transcript lifecycle events into durable operation state."""

    def __init__(self, close_unfinished: bool = True) -> None:
        self.close_unfinished = bool(close_unfinished)

    def reduce(self, events: List[Dict[str, Any]]) -> OperationLogState:
        state = OperationLogState()
        for event in events:
            event_type = str(event.get("type") or "")
            payload = dict(event.get("payload") or {})
            timestamp = str(event.get("ts") or "")
            if event_type == "operation_started":
                self._start_explicit_operation(state, payload, timestamp)
            elif event_type == "operation_finished":
                self._finish_operation(state, payload, timestamp)
            elif event_type == "operation_interrupted":
                self._interrupt_operation(state, payload, timestamp)
        if self.close_unfinished:
            self._interrupt_unfinished_operations(state)
        return state

    def _remember(self, state: OperationLogState, record: OperationRecord) -> OperationRecord:
        existing = state.operations.get(record.operation_id)
        if existing is None:
            state.operations[record.operation_id] = record
            state.order.append(record.operation_id)
            return record
        if existing.status in (_FINISHED, _INTERRUPTED):
            return existing
        existing.kind = record.kind or existing.kind
        existing.turn_id = record.turn_id or existing.turn_id
        existing.step_id = record.step_id or existing.step_id
        existing.tool_call_id = record.tool_call_id or existing.tool_call_id
        existing.parent_operation_id = record.parent_operation_id or existing.parent_operation_id
        existing.started_at = record.started_at or existing.started_at
        existing.retryable = bool(record.retryable)
        existing.metadata.update(record.metadata)
        return existing

    def _start_explicit_operation(
        self, state: OperationLogState, payload: Dict[str, Any], timestamp: str
    ) -> None:
        operation_id = str(payload.get("operation_id") or "").strip()
        if not operation_id:
            return
        self._remember(
            state,
            OperationRecord(
                operation_id=operation_id,
                kind=str(payload.get("kind") or "operation"),
                turn_id=str(payload.get("turn_id") or ""),
                step_id=str(payload.get("step_id") or ""),
                tool_call_id=str(payload.get("tool_call_id") or payload.get("call_id") or ""),
                parent_operation_id=str(payload.get("parent_operation_id") or ""),
                started_at=str(payload.get("started_at") or timestamp),
                retryable=bool(payload.get("retryable")),
                metadata=dict(payload.get("metadata") or {}),
            ),
        )

    def _finish_operation(
        self, state: OperationLogState, payload: Dict[str, Any], timestamp: str
    ) -> None:
        operation_id = str(payload.get("operation_id") or "").strip()
        if not operation_id:
            return
        record = state.operations.get(operation_id)
        if record is None:
            record = self._remember(
                state,
                OperationRecord(
                    operation_id=operation_id,
                    kind=str(payload.get("kind") or "operation"),
                    started_at=str(payload.get("started_at") or timestamp),
                ),
            )
        record.status = _FINISHED
        record.finished_at = str(payload.get("finished_at") or timestamp)
        record.result = dict(payload.get("result") or {})
        record.interrupted_reason = ""

    def _interrupt_operation(
        self, state: OperationLogState, payload: Dict[str, Any], timestamp: str
    ) -> None:
        operation_id = str(payload.get("operation_id") or "").strip()
        if not operation_id:
            return
        record = state.operations.get(operation_id)
        if record is None:
            record = self._remember(
                state,
                OperationRecord(
                    operation_id=operation_id,
                    kind=str(payload.get("kind") or "operation"),
                    started_at=str(payload.get("started_at") or timestamp),
                ),
            )
        record.status = _INTERRUPTED
        record.finished_at = str(payload.get("finished_at") or timestamp)
        record.interrupted_reason = str(
            payload.get("reason") or payload.get("interrupted_reason") or "operation_interrupted"
        )
        record.retryable = bool(payload.get("retryable"))
        record.result = dict(payload.get("result") or {})

    def _interrupt_unfinished_operations(self, state: OperationLogState) -> None:
        for operation_id in state.order:
            record = state.operations[operation_id]
            if record.status != _STARTED:
                continue
            record.status = _INTERRUPTED
            record.interrupted_reason = "restore_incomplete_operation"
            record.retryable = False


def operation_diagnostics(state: OperationLogState) -> Dict[str, Any]:
    kinds: Dict[str, Dict[str, int]] = {}
    interrupted: List[Dict[str, Any]] = []
    active: List[Dict[str, Any]] = []
    latest: List[Dict[str, Any]] = []
    for operation_id in state.order:
        record = state.operations[operation_id]
        kind = record.kind or "operation"
        counts = kinds.setdefault(kind, {"started": 0, "finished": 0, "interrupted": 0, "total": 0})
        counts["total"] += 1
        counts[record.status] = counts.get(record.status, 0) + 1
        entry = {
            "operation_id": record.operation_id,
            "kind": record.kind,
            "status": record.status,
            "turn_id": record.turn_id,
            "step_id": record.step_id,
            "tool_call_id": record.tool_call_id,
            "interrupted_reason": record.interrupted_reason,
        }
        if record.status == _INTERRUPTED:
            interrupted.append(entry)
        elif record.status == _STARTED:
            active.append(entry)
        latest.append(entry)
    return {
        "total_count": len(state.operations),
        "started_count": state.started_count,
        "finished_count": state.finished_count,
        "interrupted_count": state.interrupted_count,
        "kinds": kinds,
        "active": active[-8:],
        "interrupted": interrupted[-8:],
        "latest": latest[-12:],
    }
