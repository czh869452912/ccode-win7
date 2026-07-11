from __future__ import annotations

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
