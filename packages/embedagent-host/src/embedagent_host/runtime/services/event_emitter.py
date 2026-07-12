from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

EventHandler = Callable[[str, str, Dict[str, Any]], None]

logger = logging.getLogger(__name__)


class EventEmitter(object):
    """Broadcasts live session events to registered handlers."""

    def __init__(self) -> None:
        self._handlers = {}  # type: Dict[str, List[EventHandler]]
        self._global_handlers = []  # type: List[EventHandler]

    def add_handler(self, event_type: Optional[str], handler: EventHandler) -> None:
        if event_type is None:
            if handler not in self._global_handlers:
                self._global_handlers.append(handler)
        else:
            handlers = self._handlers.setdefault(event_type, [])
            if handler not in handlers:
                handlers.append(handler)

    def remove_handler(self, event_type: Optional[str], handler: EventHandler) -> None:
        if event_type is None:
            if handler in self._global_handlers:
                self._global_handlers.remove(handler)
        else:
            handlers = self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

    def emit(
        self,
        event_handler: Optional[EventHandler],
        event_name: str,
        session_id: str,
        payload: Dict[str, Any],
    ) -> None:
        handlers = []
        if event_handler is not None:
            handlers.append(event_handler)
        handlers.extend(self._global_handlers)
        handlers.extend(self._handlers.get(event_name, []))
        for handler in handlers:
            try:
                handler(event_name, session_id, payload)
            except (RuntimeError, ValueError, TypeError, OSError):
                logger.exception("Event handler failed for %s", event_name)

    def emit_with_snapshot(
        self,
        event_handler: Optional[EventHandler],
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
        event_handler: Optional[EventHandler],
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
        handler("session_status", session_id, {"session_snapshot": snapshot})
