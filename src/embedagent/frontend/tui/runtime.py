from __future__ import annotations

import threading
from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional

from embedagent_protocol import SessionEventEnvelope

_REQUIRED_HOST_METHODS = (
    "list_sessions",
    "create_session",
    "resume_session",
    "get_session_bootstrap",
    "set_session_mode",
    "submit_user_message",
    "respond_to_interaction",
    "cancel_session",
    "load_session_summary",
    "list_tasks",
    "get_workspace_snapshot",
    "list_workspace_tree",
    "read_workspace_file",
    "write_workspace_file",
)


def _required_session_id(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("session_id must be a string")
    session_id = value.strip()
    if not session_id:
        raise ValueError("session_id is required")
    return session_id


def _bootstrap_cursor(payload: Dict[str, Any]) -> int:
    value = payload.get("event_cursor", 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("event_cursor must be an integer")
    if value < 0:
        raise ValueError("event_cursor must be non-negative")
    return value


def _snapshot_session_id(payload: Dict[str, Any]) -> str:
    snapshot = payload.get("snapshot")
    if not isinstance(snapshot, dict):
        raise TypeError("session bootstrap snapshot must be a mapping")
    return _required_session_id(snapshot.get("session_id"))


class TerminalRuntime(object):
    """Single owner of TUI Host calls and canonical session-event ordering."""

    def __init__(
        self,
        host,
        dispatch: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        for name in _REQUIRED_HOST_METHODS:
            if not callable(getattr(host, name, None)):
                raise TypeError("host_method_missing:%s" % name)
        self._host = host
        self._dispatch = dispatch if callable(dispatch) else lambda action: None
        self._lock = threading.RLock()
        self._selected_session_id = ""
        self._event_cursor = 0
        self._generation = 0
        self._activating = False
        self._recovering = False
        self._buffered_events: List[SessionEventEnvelope] = []
        self._closed = False

    @property
    def selected_session_id(self) -> str:
        with self._lock:
            return self._selected_session_id

    @property
    def event_cursor(self) -> int:
        with self._lock:
            return self._event_cursor

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def _assert_open(self) -> None:
        if self._closed:
            raise RuntimeError("terminal_runtime_closed")

    def _dispatch_action(self, action: Dict[str, Any]) -> None:
        with self._lock:
            if self._closed:
                return
            self._dispatch(deepcopy(action))

    def activate_session(self, session_id: str, reason: str = "activate") -> Dict[str, Any]:
        selected_session_id = _required_session_id(session_id)
        with self._lock:
            self._assert_open()
            self._generation += 1
            generation = self._generation
            self._selected_session_id = selected_session_id
            self._event_cursor = 0
            self._activating = True
            self._buffered_events = []
        try:
            raw_payload = self._host.get_session_bootstrap(selected_session_id)
            if not isinstance(raw_payload, dict):
                raise TypeError("session bootstrap must be a mapping")
            payload = deepcopy(raw_payload)
            if _snapshot_session_id(payload) != selected_session_id:
                raise ValueError("session bootstrap id mismatch")
            cursor = _bootstrap_cursor(payload)
        except (OSError, RuntimeError, TypeError, ValueError):
            with self._lock:
                if generation == self._generation:
                    self._activating = False
                    self._buffered_events = []
            raise
        with self._lock:
            if self._closed or generation != self._generation:
                return {}
            self._event_cursor = cursor
            buffered = sorted(self._buffered_events, key=lambda item: item.sequence)
            self._buffered_events = []
            self._activating = False
        self._dispatch_action(
            {
                "type": "session_activated",
                "session_id": selected_session_id,
                "event_cursor": cursor,
                "generation": generation,
                "reason": str(reason or "activate"),
                "bootstrap": payload,
            }
        )
        for envelope in buffered:
            self.on_session_event(envelope)
        return payload

    def _recover_selected_session(self) -> None:
        with self._lock:
            if self._closed or self._recovering or not self._selected_session_id:
                return
            self._recovering = True
            session_id = self._selected_session_id
        try:
            self.activate_session(session_id, reason="recovery")
        finally:
            with self._lock:
                self._recovering = False

    def on_session_event(self, envelope: SessionEventEnvelope) -> None:
        if not isinstance(envelope, SessionEventEnvelope):
            raise TypeError("envelope must be SessionEventEnvelope")
        recover = False
        dispatch_event = False
        with self._lock:
            if self._closed or envelope.session_id != self._selected_session_id:
                return
            if self._activating:
                self._buffered_events.append(envelope)
                return
            if envelope.sequence <= self._event_cursor:
                return
            if envelope.sequence != self._event_cursor + 1:
                recover = not self._recovering
            else:
                self._event_cursor = envelope.sequence
                dispatch_event = True
        if recover:
            self._recover_selected_session()
            return
        if dispatch_event:
            self._dispatch_action({"type": "session_event", "event": envelope.to_dict()})

    def list_sessions(self, limit: int = 10):
        with self._lock:
            self._assert_open()
        return self._host.list_sessions(limit=max(1, int(limit)))

    def create_session(self, mode: str) -> Dict[str, Any]:
        with self._lock:
            self._assert_open()
        snapshot = self._host.create_session(mode, event_handler=self.on_session_event)
        if not isinstance(snapshot, dict):
            raise TypeError("session snapshot must be a mapping")
        return self.activate_session(_required_session_id(snapshot.get("session_id")), "create")

    def resume_session(self, reference: str, mode: str) -> Dict[str, Any]:
        with self._lock:
            self._assert_open()
        snapshot = self._host.resume_session(
            reference,
            mode,
            event_handler=self.on_session_event,
        )
        if not isinstance(snapshot, dict):
            raise TypeError("session snapshot must be a mapping")
        return self.activate_session(_required_session_id(snapshot.get("session_id")), "resume")

    def set_session_mode(self, session_id: str, mode: str) -> Dict[str, Any]:
        with self._lock:
            self._assert_open()
        self._host.set_session_mode(_required_session_id(session_id), mode)
        return self.activate_session(session_id, "mode_changed")

    def submit_user_message(self, session_id: str, text: str):
        with self._lock:
            self._assert_open()
        return self._host.submit_user_message(
            session_id=_required_session_id(session_id),
            text=text,
            stream=True,
            wait=False,
            permission_resolver=None,
            user_input_resolver=None,
            event_handler=self.on_session_event,
        )

    def respond_to_interaction(
        self,
        session_id: str,
        interaction_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        with self._lock:
            self._assert_open()
        result = self._host.respond_to_interaction(
            _required_session_id(session_id), interaction_id, payload
        )
        self.activate_session(session_id, "interaction_response")
        return result

    def cancel_session(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            self._assert_open()
        result = self._host.cancel_session(_required_session_id(session_id))
        self.activate_session(session_id, "cancel")
        return result

    def load_session_summary(self, reference: str):
        with self._lock:
            self._assert_open()
        if not str(reference or "").strip():
            return None
        return self._host.load_session_summary(reference)

    def list_tasks(self, session_id: str = "") -> Dict[str, Any]:
        with self._lock:
            self._assert_open()
        return self._host.list_tasks(session_id=session_id)

    def get_workspace_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            self._assert_open()
        return self._host.get_workspace_snapshot()

    def list_workspace_tree(
        self, path: str = ".", max_depth: int = 3, limit: int = 200
    ) -> Dict[str, Any]:
        with self._lock:
            self._assert_open()
        return self._host.list_workspace_tree(path=path, max_depth=max_depth, limit=limit)

    def read_workspace_file(self, path: str) -> Dict[str, Any]:
        with self._lock:
            self._assert_open()
        return self._host.read_workspace_file(path)

    def write_workspace_file(self, path: str, content: str) -> Dict[str, Any]:
        with self._lock:
            self._assert_open()
        return self._host.write_workspace_file(path, content)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._generation += 1
            self._activating = False
            self._recovering = False
            self._buffered_events = []
