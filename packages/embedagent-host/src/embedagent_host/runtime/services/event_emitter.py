from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from embedagent_host.runtime.session_event_protocol import SessionEventEncoder, SessionEventHandler

logger = logging.getLogger(__name__)


class EventEmitter(object):
    """Broadcasts live session events to registered handlers."""

    def __init__(self) -> None:
        self._handlers = {}  # type: Dict[str, List[SessionEventHandler]]
        self._global_handlers = []  # type: List[SessionEventHandler]
        self._encoder = SessionEventEncoder()

    def add_handler(self, event_type: Optional[str], handler: SessionEventHandler) -> None:
        if event_type is None:
            if handler not in self._global_handlers:
                self._global_handlers.append(handler)
        else:
            handlers = self._handlers.setdefault(event_type, [])
            if handler not in handlers:
                handlers.append(handler)

    def remove_handler(self, event_type: Optional[str], handler: SessionEventHandler) -> None:
        if event_type is None:
            if handler in self._global_handlers:
                self._global_handlers.remove(handler)
        else:
            handlers = self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

    def emit(
        self,
        event_handler: Optional[SessionEventHandler],
        event_name: str,
        session_id: str,
        payload: Dict[str, Any],
    ) -> None:
        with self._encoder.session_scope(session_id):
            handlers = []  # type: List[SessionEventHandler]
            envelope = self._encoder.encode(session_id, event_name, payload)
            if event_handler is not None:
                handlers.append(event_handler)
            handlers.extend(self._global_handlers)
            handlers.extend(self._handlers.get(event_name, []))
            for handler in handlers:
                try:
                    handler(envelope)
                except (RuntimeError, ValueError, TypeError, OSError):
                    logger.exception("Event handler failed for %s", event_name)

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
        event_handler: Optional[SessionEventHandler],
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
        self.emit(event_handler, event_name, session_id, data)

    def notify_status(
        self,
        event_handler: Optional[SessionEventHandler],
        session_id: str,
        snapshot_provider: Callable[[], Dict[str, Any]],
    ) -> None:
        handler = event_handler
        if handler is None:
            return
        try:
            snapshot = snapshot_provider()
        except (RuntimeError, ValueError, TypeError, OSError):
            logger.exception("Failed to get session snapshot for status notification")
            return
        self.emit(handler, "session_status", session_id, {"session_snapshot": snapshot})
