from __future__ import annotations

import threading
import uuid
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Protocol


class SessionLeaseConflict(RuntimeError):
    pass


class SessionLogPort(Protocol):
    def append_event(
        self,
        session_id: str,
        event_type: str,
        payload: Dict[str, Any],
        event_id: str = "",
        ts: str = "",
        schema_version: int = 2,
    ) -> Any:
        raise NotImplementedError

    def transcript_exists(self, session_id: str) -> bool:
        raise NotImplementedError

    def load_events(self, session_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def acquire_lease(self, session_id: str) -> Any:
        raise NotImplementedError


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _require_session_id(session_id: str) -> str:
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        raise ValueError("session_id is required")
    return normalized_session_id


class InMemorySessionLog(object):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._events = {}  # type: Dict[str, List[Dict[str, Any]]]
        self._leased_session_ids = set()

    def append_event(
        self,
        session_id: str,
        event_type: str,
        payload: Dict[str, Any],
        event_id: str = "",
        ts: str = "",
        schema_version: int = 2,
    ) -> Dict[str, Any]:
        if schema_version != 2:
            raise ValueError("transcript events must use schema_version 2")
        normalized_session_id = _require_session_id(session_id)
        stored_payload = deepcopy(payload or {})
        with self._lock:
            events = self._events.setdefault(normalized_session_id, [])
            event = {
                "schema_version": 2,
                "session_id": normalized_session_id,
                "event_id": event_id or ("evt-" + uuid.uuid4().hex[:12]),
                "seq": len(events) + 1,
                "ts": ts or _utc_now(),
                "type": event_type,
                "parent_message_id": stored_payload.get("parent_message_id", ""),
                "payload": stored_payload,
            }
            events.append(event)
            return deepcopy(event)

    def transcript_exists(self, session_id: str) -> bool:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return False
        with self._lock:
            return bool(self._events.get(normalized_session_id))

    def load_events(self, session_id: str) -> List[Dict[str, Any]]:
        normalized_session_id = _require_session_id(session_id)
        with self._lock:
            return deepcopy(self._events.get(normalized_session_id, []))

    @contextmanager
    def acquire_lease(self, session_id: str) -> Any:
        normalized_session_id = _require_session_id(session_id)
        with self._lock:
            if normalized_session_id in self._leased_session_ids:
                raise SessionLeaseConflict(
                    "session log lease is already held: %s" % normalized_session_id
                )
            self._leased_session_ids.add(normalized_session_id)
        try:
            yield
        finally:
            with self._lock:
                self._leased_session_ids.discard(normalized_session_id)
