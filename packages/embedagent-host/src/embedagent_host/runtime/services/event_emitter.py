from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from embedagent_protocol import SessionEventSink

from embedagent_host.runtime.session_event_protocol import SessionEventEncoder

logger = logging.getLogger(__name__)


class EventEmitter(object):
    """Encodes and publishes live events to one construction-bound sink."""

    def __init__(self, sink: Optional[SessionEventSink] = None) -> None:
        self._sink = sink
        self._encoder = SessionEventEncoder()

    def emit(
        self,
        event_name: str,
        session_id: str,
        payload: Dict[str, Any],
    ) -> None:
        with self._encoder.session_scope(session_id):
            envelope = self._encoder.encode(session_id, event_name, payload)
            if self._sink is not None:
                self._sink.on_session_event(envelope)

    def current_cursor(self, session_id: str) -> int:
        return self._encoder.current_sequence(session_id)

    def capture(
        self,
        session_id: str,
        projection_loader: Callable[[], Dict[str, Any]],
    ) -> Dict[str, Any]:
        with self._encoder.session_scope(session_id):
            payload = dict(projection_loader() or {})
            payload["event_cursor"] = self._encoder.current_sequence(session_id)
            return payload

    def emit_with_snapshot(
        self,
        event_name: str,
        session_id: str,
        payload: Dict[str, Any],
        snapshot_provider: Callable[[], Dict[str, Any]],
    ) -> None:
        data = dict(payload)
        try:
            data["session_snapshot"] = snapshot_provider()
        except (RuntimeError, ValueError, TypeError, OSError):
            logger.exception("Failed to get session snapshot for event %s", event_name)
        self.emit(event_name, session_id, data)

    def notify_status(
        self,
        session_id: str,
        snapshot_provider: Callable[[], Dict[str, Any]],
    ) -> None:
        if self._sink is None:
            return
        try:
            snapshot = snapshot_provider()
        except (RuntimeError, ValueError, TypeError, OSError):
            logger.exception("Failed to get session snapshot for status notification")
            return
        self.emit("session_status", session_id, {"session_snapshot": snapshot})
