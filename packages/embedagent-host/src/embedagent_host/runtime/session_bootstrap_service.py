from __future__ import annotations

from typing import Any, Callable, Dict


class SessionBootstrapService(object):
    def __init__(
        self,
        snapshot_loader: Callable[[str], Dict[str, Any]],
        history_loader: Callable[[str], Dict[str, Any]],
        plan_loader: Callable[[str], Any],
        permission_context_loader: Callable[[str], Any],
        capability_loader: Callable[[str], Dict[str, Any]] = None,
    ) -> None:
        self._snapshot_loader = snapshot_loader
        self._history_loader = history_loader
        self._plan_loader = plan_loader
        self._permission_context_loader = permission_context_loader
        self._capability_loader = capability_loader

    def build(self, session_id: str) -> Dict[str, Any]:
        safe_session_id = str(session_id or "")
        return {
            "snapshot": self._snapshot_loader(safe_session_id),
            "history": self._history_loader(safe_session_id),
            "plan": self._plan_loader(safe_session_id),
            "permission_context": self._permission_context_loader(safe_session_id),
            "capabilities": (
                self._capability_loader(safe_session_id)
                if callable(self._capability_loader)
                else {}
            ),
        }
