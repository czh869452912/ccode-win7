from __future__ import annotations

from typing import Any, Callable


class ManagedSessionRestorePolicy(object):
    """Expose only the Host-validated transcript prefix to Agent Core."""

    def __init__(self, managed_session_lookup: Callable[[str], Any]) -> None:
        if not callable(managed_session_lookup):
            raise TypeError("managed_session_lookup must be callable")
        self._managed_session_lookup = managed_session_lookup

    def trusted_event_count(self, session_id: str) -> int:
        try:
            state = self._managed_session_lookup(session_id)
        except (KeyError, ValueError):
            return 0
        if state is None:
            return 0
        lock = getattr(state, "lock", None)
        if lock is None:
            return max(0, int(getattr(state, "best_effort_restore_event_count", 0) or 0))
        with lock:
            return max(0, int(getattr(state, "best_effort_restore_event_count", 0) or 0))
