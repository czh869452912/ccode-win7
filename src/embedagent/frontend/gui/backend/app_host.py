from __future__ import annotations

import os
import threading
from typing import Any, Callable, Dict, Optional

from embedagent.protocol import CoreInterface

from .workspace_registry import WorkspaceRegistry, canonical_workspace_path


class NoActiveWorkspaceError(Exception):
    pass


class GUIAppHost(object):
    def __init__(
        self,
        core_factory: Callable[[str], CoreInterface],
        registry: Optional[WorkspaceRegistry] = None,
    ) -> None:
        self._core_factory = core_factory
        self._registry = registry or WorkspaceRegistry()
        self._lock = threading.RLock()
        self._frontend = None
        self._active_core = None  # type: Optional[CoreInterface]
        self._active_workspace = None  # type: Optional[Dict[str, Any]]
        self._last_error = ""

    def bind_frontend(self, frontend: Any) -> None:
        with self._lock:
            self._frontend = frontend
            if self._active_core is not None:
                self._active_core.register_frontend(frontend)

    def current_core(self) -> Optional[CoreInterface]:
        with self._lock:
            return self._active_core

    def require_core(self) -> CoreInterface:
        core = self.current_core()
        if core is None:
            raise NoActiveWorkspaceError("no_active_workspace")
        return core

    def bootstrap(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "workspaces": self._registry.list_workspaces(),
                "active_workspace": (
                    dict(self._active_workspace) if self._active_workspace else None
                ),
                "has_active_workspace": self._active_core is not None,
                "last_error": self._last_error,
            }

    def list_workspaces(self) -> Dict[str, Any]:
        payload = self.bootstrap()
        return {
            "workspaces": payload["workspaces"],
            "active_workspace": payload["active_workspace"],
        }

    def open_workspace_path(self, path: str, label: str = "") -> Dict[str, Any]:
        record = self._registry.upsert_path(path, label=label)
        return self.activate_workspace(record["id"])

    def activate_workspace(self, workspace_id: str) -> Dict[str, Any]:
        with self._lock:
            record = self._registry.get(workspace_id)
            if record is None:
                raise ValueError("workspace_not_found")
            path = canonical_workspace_path(record["path"])
            if not os.path.isdir(path):
                raise ValueError("workspace_not_found")
            if self._active_workspace and self._active_workspace.get("id") == record["id"]:
                refreshed = self._registry.mark_opened(record["id"]) or record
                self._active_workspace = refreshed
                return self.bootstrap()
            previous = self._active_core
            try:
                next_core = self._core_factory(path)
                if self._frontend is not None:
                    next_core.register_frontend(self._frontend)
            except Exception as exc:
                self._last_error = str(exc)
                raise
            if previous is not None:
                previous.shutdown()
            refreshed = self._registry.mark_opened(record["id"]) or record
            self._active_core = next_core
            self._active_workspace = refreshed
            self._last_error = ""
            self._broadcast_workspace_changed()
            return self.bootstrap()

    def remove_workspace(self, workspace_id: str) -> Dict[str, Any]:
        with self._lock:
            active_removed = bool(
                self._active_workspace and self._active_workspace.get("id") == workspace_id
            )
            removed = self._registry.remove(workspace_id)
            if active_removed:
                if self._active_core is not None:
                    self._active_core.shutdown()
                self._active_core = None
                self._active_workspace = None
                self._broadcast_workspace_changed()
            payload = self.bootstrap()
            payload["removed"] = removed
            return payload

    def shutdown(self) -> None:
        with self._lock:
            core = self._active_core
            self._active_core = None
            self._active_workspace = None
        if core is not None:
            core.shutdown()

    def _broadcast_workspace_changed(self) -> None:
        frontend = self._frontend
        dispatch = getattr(frontend, "_dispatch_message", None)
        if callable(dispatch):
            dispatch({"type": "workspace_changed", "data": self.bootstrap()})


class SingleWorkspaceAppHost(object):
    def __init__(self, core: CoreInterface) -> None:
        self._core = core

    def bind_frontend(self, frontend: Any) -> None:
        self._core.register_frontend(frontend)

    def current_core(self) -> Optional[CoreInterface]:
        return self._core

    def require_core(self) -> CoreInterface:
        return self._core

    def bootstrap(self) -> Dict[str, Any]:
        workspace = None
        try:
            snapshot = self._core.get_workspace_snapshot()
            path = (
                snapshot.get("path")
                if isinstance(snapshot, dict)
                else getattr(snapshot, "path", "")
            )
            if path:
                workspace = {
                    "id": "active",
                    "path": path,
                    "label": os.path.basename(path) or path,
                    "exists": os.path.isdir(path),
                    "created_at": "",
                    "last_opened_at": "",
                }
        except (OSError, ValueError, TypeError, AttributeError):
            workspace = None
        return {
            "workspaces": [workspace] if workspace else [],
            "active_workspace": workspace,
            "has_active_workspace": True,
            "last_error": "",
        }

    def list_workspaces(self) -> Dict[str, Any]:
        payload = self.bootstrap()
        return {
            "workspaces": payload["workspaces"],
            "active_workspace": payload["active_workspace"],
        }

    def open_workspace_path(self, path: str, label: str = "") -> Dict[str, Any]:
        raise ValueError("workspace_switch_unavailable")

    def activate_workspace(self, workspace_id: str) -> Dict[str, Any]:
        raise ValueError("workspace_switch_unavailable")

    def remove_workspace(self, workspace_id: str) -> Dict[str, Any]:
        raise ValueError("workspace_switch_unavailable")

    def shutdown(self) -> None:
        self._core.shutdown()
