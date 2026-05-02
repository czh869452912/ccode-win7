"""Structured execution tracing for agent loop observability."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class TraceEventType(Enum):
    TURN_START = "turn_start"
    LLM_CALL_START = "llm_call_start"
    LLM_CALL_END = "llm_call_end"
    LLM_RETRY = "llm_retry"
    TOOL_EXECUTION_START = "tool_execution_start"
    TOOL_EXECUTION_END = "tool_execution_end"
    TOOL_PARALLEL_BATCH = "tool_parallel_batch"
    PERMISSION_REQUEST = "permission_request"
    PERMISSION_DECISION = "permission_decision"
    STATE_TRANSITION = "state_transition"
    CHECKPOINT_SUSPEND = "checkpoint_suspend"
    CHECKPOINT_RESUME = "checkpoint_resume"
    TURN_END = "turn_end"
    ERROR = "error"


class TraceEvent(object):
    def __init__(
        self,
        event_type: TraceEventType,
        timestamp: float,
        turn_id: str,
        step_id: Optional[str],
        session_id: str,
        data: Dict[str, Any],
        duration_ms: Optional[int] = None,
    ) -> None:
        self.event_type = event_type
        self.timestamp = timestamp
        self.turn_id = turn_id
        self.step_id = step_id
        self.session_id = session_id
        self.data = data
        self.duration_ms = duration_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "turn_id": self.turn_id,
            "step_id": self.step_id,
            "session_id": self.session_id,
            "data": self.data,
            "duration_ms": self.duration_ms,
        }


class ExecutionTracer(object):
    """Records structured execution traces for agent loop observability."""

    def __init__(self, output_dir: Optional[str] = None) -> None:
        self.output_dir = output_dir
        self._buffer = []  # type: List[TraceEvent]
        self._buffer_limit = 100

    def record(
        self,
        event_type: TraceEventType,
        session_id: str,
        turn_id: str,
        step_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
    ) -> TraceEvent:
        event = TraceEvent(
            event_type=event_type,
            timestamp=time.time(),
            turn_id=turn_id,
            step_id=step_id,
            session_id=session_id,
            data=data or {},
            duration_ms=duration_ms,
        )
        self._buffer.append(event)
        if len(self._buffer) >= self._buffer_limit:
            self.flush()
        return event

    @contextmanager
    def start_span(
        self,
        event_type: TraceEventType,
        session_id: str,
        turn_id: str,
        step_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        start_time = time.time()
        self.record(event_type, session_id, turn_id, step_id, data)
        try:
            yield
        except BaseException as exc:
            self.record(
                TraceEventType.ERROR,
                session_id,
                turn_id,
                step_id,
                data={"error_type": type(exc).__name__, "error_message": str(exc)},
            )
            raise
        finally:
            duration_ms = int((time.time() - start_time) * 1000)
            self.record(
                TraceEventType.LLM_CALL_END if event_type == TraceEventType.LLM_CALL_START else TraceEventType.TURN_END,
                session_id,
                turn_id,
                step_id,
                data=data or {},
                duration_ms=duration_ms,
            )

    def flush(self) -> None:
        if not self._buffer or not self.output_dir:
            self._buffer = []
            return

        # Group by session_id and date
        from collections import defaultdict
        events_by_file = defaultdict(list)
        for event in self._buffer:
            date_str = datetime.fromtimestamp(event.timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
            filename = "{}_{}.jsonl".format(event.session_id, date_str)
            events_by_file[filename].append(event)

        for filename, events in events_by_file.items():
            filepath = os.path.join(self.output_dir, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "a", encoding="utf-8") as f:
                for event in events:
                    f.write(json.dumps(event.to_dict(), default=str) + "\n")

        self._buffer = []

    def get_traces(
        self,
        session_id: Optional[str] = None,
        turn_id: Optional[str] = None,
    ) -> List[TraceEvent]:
        traces = []
        for event in self._buffer:
            if session_id is not None and event.session_id != session_id:
                continue
            if turn_id is not None and event.turn_id != turn_id:
                continue
            traces.append(event)
        return traces

    def summary(self, session_id: str) -> Dict[str, Any]:
        traces = self.get_traces(session_id=session_id)
        turn_count = 0
        total_tool_calls = 0
        total_llm_calls = 0
        error_count = 0
        total_duration_ms = 0
        turn_durations = []

        for event in traces:
            if event.event_type == TraceEventType.TURN_START:
                turn_count += 1
            elif event.event_type == TraceEventType.LLM_CALL_START:
                total_llm_calls += 1
            elif event.event_type == TraceEventType.TOOL_EXECUTION_START:
                total_tool_calls += 1
            elif event.event_type == TraceEventType.ERROR:
                error_count += 1
            elif event.event_type == TraceEventType.TURN_END and event.duration_ms:
                turn_durations.append(event.duration_ms)

        avg_turn_duration_ms = 0
        if turn_durations:
            avg_turn_duration_ms = sum(turn_durations) // len(turn_durations)

        return {
            "turn_count": turn_count,
            "total_tool_calls": total_tool_calls,
            "total_llm_calls": total_llm_calls,
            "error_count": error_count,
            "avg_turn_duration_ms": avg_turn_duration_ms,
        }
