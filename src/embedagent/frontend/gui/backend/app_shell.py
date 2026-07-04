from __future__ import annotations

import sys
from typing import Any, Dict, Optional

APP_SHELL_VERSION = 1

_SECRET_KEY_PARTS = (
    "api_key",
    "authorization",
    "password",
    "secret",
    "token",
)
_BLOCKED_TOP_LEVEL_KEYS = (
    "prompt",
    "transcript",
    "tool_output",
)


def _is_blocked_key(key: Any) -> bool:
    lowered = str(key or "").lower()
    if any(part in lowered for part in _SECRET_KEY_PARTS):
        return True
    return lowered in _BLOCKED_TOP_LEVEL_KEYS


def _safe_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            if _is_blocked_key(key):
                continue
            safe[str(key)] = _safe_mapping(item)
        return safe
    if isinstance(value, (list, tuple)):
        return [_safe_mapping(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class AppShellService(object):
    def __init__(
        self,
        app_host: Any,
        host_diagnostics: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._app_host = app_host
        self._host_diagnostics = host_diagnostics if host_diagnostics is not None else {}
        self._settings = dict(settings or {})

    def bootstrap(self) -> Dict[str, Any]:
        return self._base_payload(self._app_host.bootstrap())

    def list_workspaces(self) -> Dict[str, Any]:
        return self._base_payload(self._app_host.bootstrap())

    def open_workspace_path(self, path: str, label: str = "") -> Dict[str, Any]:
        raw = self._app_host.open_workspace_path(path, label=label)
        return self._base_payload(raw)

    def activate_workspace(self, workspace_id: str) -> Dict[str, Any]:
        raw = self._app_host.activate_workspace(workspace_id)
        return self._base_payload(raw)

    def remove_workspace(self, workspace_id: str) -> Dict[str, Any]:
        raw = self._app_host.remove_workspace(workspace_id)
        return self._base_payload(raw)

    def _base_payload(
        self, raw: Optional[Dict[str, Any]] = None, last_error: str = ""
    ) -> Dict[str, Any]:
        payload = dict(raw or {})
        workspaces = list(payload.get("workspaces") or [])
        active_workspace = payload.get("active_workspace")
        response = {
            "app": self._app_metadata(),
            "workspaces": workspaces,
            "active_workspace": (
                dict(active_workspace) if isinstance(active_workspace, dict) else None
            ),
            "has_active_workspace": bool(payload.get("has_active_workspace")),
            "diagnostics": self._diagnostics(payload),
            "capabilities": self._capabilities(),
            "settings": self._settings_payload(),
            "last_error": str(last_error or payload.get("last_error") or ""),
        }
        if "removed" in payload:
            response["removed"] = bool(payload.get("removed"))
        return response

    def _app_metadata(self) -> Dict[str, Any]:
        return {
            "shell_version": APP_SHELL_VERSION,
            "product_name": "EmbedAgent",
            "protocol": "gui_app_shell_v1",
        }

    def _capabilities(self) -> Dict[str, Any]:
        capabilities = {
            "app_commands": [
                "app.settings",
                "app.diagnostics",
                "app.source_control",
                "app.reload",
            ],
            "workspace_commands": [
                "workspace.open",
                "workspace.refresh",
                "workspace.remove_current",
            ],
            "surfaces": {
                "right_panel": self._right_panel_surfaces(),
                "bottom_drawer": self._bottom_drawer_surfaces(),
            },
            "keybindings": self._keybindings(),
            "source_control": {
                "enabled": True,
                "vcs": ["git"],
                "read_only": True,
                "remote_providers": False,
                "network": False,
                "checkpoints": False,
                "requires_active_workspace": True,
            },
            "terminal": {
                "enabled": True,
                "pty": False,
                "resize": False,
                "history_persistent": False,
                "max_buffer_bytes": 131072,
            },
            "thread_lifecycle": {
                "rename": True,
                "fork": True,
                "archive": True,
            },
        }
        capabilities.update(self._active_agent_capabilities())
        return capabilities

    def _active_agent_capabilities(self) -> Dict[str, Any]:
        current_core = getattr(self._app_host, "current_core", None)
        core = current_core() if callable(current_core) else None
        get_session_capabilities = getattr(core, "get_session_capabilities", None)
        if not callable(get_session_capabilities):
            return {}
        try:
            source = get_session_capabilities("")
        except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
            return {}
        if not isinstance(source, dict):
            return {}
        projected = {}
        for key in ("agentApplication", "agentApplications", "emptyState"):
            if key in source:
                projected[key] = _safe_mapping(source.get(key))
        return projected

    def _keybindings(self) -> list:
        return [
            {
                "key": "mod+k",
                "command_id": "palette.open",
                "when": "not_palette",
            },
            {
                "key": "escape",
                "command_id": "palette.close",
                "when": "palette",
            },
            {
                "key": "escape",
                "command_id": "message.stop",
                "when": "running",
            },
            {
                "key": "mod+b",
                "command_id": "view.toggle_right_panel",
                "when": "always",
            },
            {
                "key": "mod+,",
                "command_id": "app.settings",
                "when": "always",
            },
            {
                "key": "mod+j",
                "command_id": "view.toggle_bottom_drawer",
                "when": "always",
            },
            {
                "key": "mod+1",
                "command_id": "surface.files",
                "when": "always",
            },
            {
                "key": "mod+2",
                "command_id": "surface.terminal",
                "when": "always",
            },
            {
                "key": "mod+3",
                "command_id": "surface.diff",
                "when": "always",
            },
            {
                "key": "mod+4",
                "command_id": "surface.preview",
                "when": "always",
            },
            {
                "key": "mod+enter",
                "command_id": "message.send",
                "when": "composer",
            },
        ]

    def _right_panel_surfaces(self) -> list:
        return [
            {
                "id": "preview",
                "title": "Preview",
                "icon": "B",
                "description": "Open a local browser preview.",
                "launcher_order": 10,
                "command": True,
                "slash": "/preview",
                "visible_when": "always",
                "default_resource_id": "",
                "close_behavior": "closable",
                "keywords": ["browser", "localhost", "web"],
            },
            {
                "id": "files",
                "title": "Files",
                "icon": "F",
                "description": "Browse workspace files.",
                "launcher_order": 20,
                "command": True,
                "slash": "/workspace",
                "visible_when": "always",
                "default_resource_id": "",
                "close_behavior": "closable",
            },
            {
                "id": "terminal",
                "title": "Terminal",
                "icon": "T",
                "description": "Use a shell in this workspace.",
                "launcher_order": 30,
                "command": True,
                "slash": "",
                "visible_when": "has_session",
                "default_resource_id": "",
                "close_behavior": "closable",
            },
            {
                "id": "diff",
                "title": "Diff",
                "icon": "D",
                "description": "Review local changes.",
                "launcher_order": 40,
                "command": True,
                "slash": "/diff",
                "visible_when": "always",
                "default_resource_id": "current",
                "close_behavior": "closable",
                "keywords": ["git", "changes", "diff"],
            },
            {
                "id": "plan",
                "title": "Plan",
                "icon": "P",
                "description": "Inspect the current plan.",
                "launcher_order": 50,
                "command": True,
                "slash": "/plan",
                "visible_when": "always",
                "default_resource_id": "",
                "close_behavior": "closable",
            },
            {
                "id": "source_control",
                "title": "Source Control",
                "icon": "S",
                "description": "Review local Git status.",
                "launcher_order": 60,
                "command": True,
                "slash": "",
                "visible_when": "always",
                "default_resource_id": "",
                "close_behavior": "closable",
                "read_only": True,
                "offline": True,
                "keywords": ["git", "changes", "local"],
            },
            {
                "id": "settings",
                "title": "Settings",
                "icon": "G",
                "description": "Adjust app-shell preferences.",
                "launcher_order": 70,
                "command": True,
                "slash": "",
                "visible_when": "always",
                "default_resource_id": "",
                "close_behavior": "closable",
            },
            {
                "id": "diagnostics",
                "title": "Diagnostics",
                "icon": "I",
                "description": "Inspect app-shell health.",
                "launcher_order": 80,
                "command": True,
                "slash": "",
                "visible_when": "always",
                "default_resource_id": "",
                "close_behavior": "closable",
            },
        ]

    def _bottom_drawer_surfaces(self) -> list:
        return [
            {
                "id": "run_output",
                "title": "Run Output",
                "icon": "R",
                "description": "Show turn and tool output.",
                "launcher_order": 10,
                "command": True,
                "command_label": "Toggle Run Output",
                "visible_when": "always",
                "close_behavior": "pinned",
            },
            {
                "id": "terminal",
                "title": "Terminal",
                "icon": "T",
                "description": "Use a shell in this workspace.",
                "launcher_order": 20,
                "command": True,
                "command_label": "Open Terminal",
                "visible_when": "has_session",
                "close_behavior": "pinned",
            },
            {
                "id": "logs",
                "title": "Logs",
                "icon": "L",
                "description": "Inspect renderer and runtime logs.",
                "launcher_order": 30,
                "command": True,
                "command_label": "Open Logs",
                "visible_when": "always",
                "close_behavior": "pinned",
            },
        ]

    def _settings_payload(self) -> Dict[str, Any]:
        payload = {
            "confirm_workspace_switch": True,
            "show_diagnostics_badge": True,
        }
        for key in payload:
            if key in self._settings:
                payload[key] = bool(self._settings.get(key))
        return payload

    def _diagnostics(self, raw: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raw_payload = dict(raw or {})
        safe_host = _safe_mapping(self._host_diagnostics)
        if not isinstance(safe_host, dict):
            safe_host = {}
        workspaces = list(raw_payload.get("workspaces") or [])
        active_workspace = raw_payload.get("active_workspace")
        current_core = getattr(self._app_host, "current_core", None)
        active_core_present = False
        if callable(current_core):
            active_core_present = current_core() is not None
        host = dict(safe_host.get("host") or {})
        if "platform" not in host:
            host["platform"] = sys.platform
        return {
            "host": host,
            "runtime": dict(safe_host.get("runtime") or {}),
            "renderer": dict(safe_host.get("renderer") or {}),
            "workspace_registry": {
                "count": len(workspaces),
                "active_workspace_id": str(
                    active_workspace.get("id") if isinstance(active_workspace, dict) else ""
                ),
                "active_workspace_path": str(
                    active_workspace.get("path") if isinstance(active_workspace, dict) else ""
                ),
            },
            "active_core": {
                "present": bool(active_core_present),
            },
        }
