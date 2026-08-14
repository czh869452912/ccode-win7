from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from embedagent_protocol import FrontendSessionPort, FrontendWorkspacePort, SessionEventSink

from .workspace_registry import WorkspaceRegistry, canonical_workspace_path


def _copy_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _copy_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy_value(item) for item in value]
    return value


@dataclass(frozen=True)
class FrontendPortSet(object):
    session: FrontendSessionPort
    workspace: FrontendWorkspacePort

    def close(self) -> None:
        self.session.close()


class NoActiveWorkspaceError(Exception):
    pass


class GUIAppHost(object):
    def __init__(
        self,
        port_factory: Callable[[str, SessionEventSink], FrontendPortSet],
        event_sink: SessionEventSink,
        registry: Optional[WorkspaceRegistry] = None,
        agent_capabilities: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not callable(port_factory):
            raise TypeError("port_factory must be callable")
        if not callable(getattr(event_sink, "on_session_event", None)):
            raise TypeError("event_sink must provide on_session_event")
        self._port_factory = port_factory
        self._event_sink = event_sink
        self._registry = registry or WorkspaceRegistry()
        self._lock = threading.RLock()
        self._active_ports = None  # type: Optional[FrontendPortSet]
        self._active_workspace = None  # type: Optional[Dict[str, Any]]
        self._agent_capabilities = _copy_value(agent_capabilities or {})
        self._last_error = ""

    def current_ports(self) -> Optional[FrontendPortSet]:
        with self._lock:
            return self._active_ports

    def current_session_port(self) -> Optional[FrontendSessionPort]:
        ports = self.current_ports()
        return ports.session if ports is not None else None

    def current_workspace_port(self) -> Optional[FrontendWorkspacePort]:
        ports = self.current_ports()
        return ports.workspace if ports is not None else None

    def agent_capabilities(self) -> Dict[str, Any]:
        with self._lock:
            return _copy_value(self._agent_capabilities)

    def require_session_port(self) -> FrontendSessionPort:
        port = self.current_session_port()
        if port is None:
            raise NoActiveWorkspaceError("no_active_workspace")
        return port

    def require_workspace_port(self) -> FrontendWorkspacePort:
        port = self.current_workspace_port()
        if port is None:
            raise NoActiveWorkspaceError("no_active_workspace")
        return port

    def bootstrap(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "workspaces": self._registry.list_workspaces(),
                "active_workspace": (
                    dict(self._active_workspace) if self._active_workspace else None
                ),
                "has_active_workspace": self._active_ports is not None,
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
            previous = self._active_ports
            self._active_ports = None
            self._active_workspace = None
            try:
                if previous is not None:
                    previous.close()
                next_ports = self._port_factory(path, self._event_sink)
                self._validate_ports(next_ports)
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                self._last_error = str(exc)
                raise
            refreshed = self._registry.mark_opened(record["id"]) or record
            self._active_ports = next_ports
            self._active_workspace = refreshed
            self._last_error = ""
            return self.bootstrap()

    def remove_workspace(self, workspace_id: str) -> Dict[str, Any]:
        with self._lock:
            active_removed = bool(
                self._active_workspace and self._active_workspace.get("id") == workspace_id
            )
            removed = self._registry.remove(workspace_id)
            if active_removed:
                if self._active_ports is not None:
                    self._active_ports.close()
                self._active_ports = None
                self._active_workspace = None
            payload = self.bootstrap()
            payload["removed"] = removed
            return payload

    def shutdown(self) -> None:
        with self._lock:
            ports = self._active_ports
            self._active_ports = None
            self._active_workspace = None
        if ports is not None:
            ports.close()

    @staticmethod
    def _validate_ports(ports: Any) -> None:
        if not isinstance(ports, FrontendPortSet):
            raise TypeError("port_factory must return a FrontendPortSet")
        if not callable(getattr(ports.session, "get_session_bootstrap", None)):
            raise TypeError("session port must provide get_session_bootstrap")
        if not callable(getattr(ports.workspace, "get_workspace_snapshot", None)):
            raise TypeError("workspace port must provide get_workspace_snapshot")


class SingleWorkspaceAppHost(object):
    def __init__(
        self,
        ports: FrontendPortSet,
        agent_capabilities: Optional[Dict[str, Any]] = None,
    ) -> None:
        GUIAppHost._validate_ports(ports)
        self._ports = ports
        self._agent_capabilities = _copy_value(agent_capabilities or {})

    def current_ports(self) -> Optional[FrontendPortSet]:
        return self._ports

    def current_session_port(self) -> Optional[FrontendSessionPort]:
        return self._ports.session if self._ports is not None else None

    def current_workspace_port(self) -> Optional[FrontendWorkspacePort]:
        return self._ports.workspace if self._ports is not None else None

    def agent_capabilities(self) -> Dict[str, Any]:
        return _copy_value(self._agent_capabilities)

    def require_session_port(self) -> FrontendSessionPort:
        port = self.current_session_port()
        if port is None:
            raise NoActiveWorkspaceError("no_active_workspace")
        return port

    def require_workspace_port(self) -> FrontendWorkspacePort:
        port = self.current_workspace_port()
        if port is None:
            raise NoActiveWorkspaceError("no_active_workspace")
        return port

    def bootstrap(self) -> Dict[str, Any]:
        workspace = None
        try:
            snapshot = self.require_workspace_port().get_workspace_snapshot()
            path = str(snapshot.get("path") or "")
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
            "has_active_workspace": self._ports is not None,
            "last_error": "",
        }

    def list_workspaces(self) -> Dict[str, Any]:
        payload = self.bootstrap()
        return {
            "workspaces": payload["workspaces"],
            "active_workspace": payload["active_workspace"],
        }

    def open_workspace_path(self, path: str, label: str = "") -> Dict[str, Any]:
        del path, label
        raise ValueError("workspace_switch_unavailable")

    def activate_workspace(self, workspace_id: str) -> Dict[str, Any]:
        del workspace_id
        raise ValueError("workspace_switch_unavailable")

    def remove_workspace(self, workspace_id: str) -> Dict[str, Any]:
        del workspace_id
        raise ValueError("workspace_switch_unavailable")

    def shutdown(self) -> None:
        ports = self._ports
        self._ports = None
        if ports is not None:
            ports.close()
