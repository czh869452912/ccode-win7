from __future__ import annotations

import sys
from typing import Any, Dict, Optional

from embedagent.frontend.gui.backend.app_shell_spec import (
    AppShellSpec,
    default_app_shell_spec,
)

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


def _string_items(value: Any) -> list:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if str(item or "").strip()]


def _id_allow_set(profile: Dict[str, Any], key: str) -> Optional[set]:
    if key not in profile:
        return None
    return set(_string_items(profile.get(key)))


def _filter_records_by_id(records: Any, allowed_ids: Optional[set]) -> list:
    items = list(records or [])
    if allowed_ids is None:
        return items
    return [
        dict(item)
        for item in items
        if isinstance(item, dict) and str(item.get("id") or "") in allowed_ids
    ]


def _filter_keybindings(records: Any, allowed_command_ids: Optional[set]) -> list:
    items = list(records or [])
    if allowed_command_ids is None:
        return items
    return [
        dict(item)
        for item in items
        if isinstance(item, dict)
        and str(item.get("command_id") or item.get("commandId") or "") in allowed_command_ids
    ]


def _selected_app_shell_profile(agent_capabilities: Dict[str, Any]) -> Dict[str, Any]:
    application = agent_capabilities.get("agentApplication")
    if not isinstance(application, dict):
        return {}
    metadata = application.get("metadata")
    if not isinstance(metadata, dict):
        return {}
    profile = metadata.get("appShell")
    if profile is None:
        profile = metadata.get("app_shell")
    return profile if isinstance(profile, dict) else {}


class AppShellService(object):
    def __init__(
        self,
        app_host: Any,
        host_diagnostics: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
        shell_spec: Optional[AppShellSpec] = None,
    ) -> None:
        self._app_host = app_host
        self._host_diagnostics = host_diagnostics if host_diagnostics is not None else {}
        self._settings = dict(settings or {})
        self._shell_spec = shell_spec or default_app_shell_spec()

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
        capabilities = self._shell_spec.capabilities()
        agent_capabilities = self._agent_capabilities()
        self._apply_agent_app_shell_profile(capabilities, agent_capabilities)
        capabilities.update(agent_capabilities)
        return capabilities

    def _apply_agent_app_shell_profile(
        self,
        capabilities: Dict[str, Any],
        agent_capabilities: Dict[str, Any],
    ) -> None:
        profile = _selected_app_shell_profile(agent_capabilities)
        if not profile:
            return
        capabilities["app_commands"] = _filter_records_by_id(
            capabilities.get("app_commands"),
            _id_allow_set(profile, "appCommandIds"),
        )
        command_palette = dict(capabilities.get("command_palette") or {})
        command_palette["groups"] = _filter_records_by_id(
            command_palette.get("groups"),
            _id_allow_set(profile, "commandPaletteGroupIds"),
        )
        capabilities["command_palette"] = command_palette

        surfaces = dict(capabilities.get("surfaces") or {})
        surfaces["right_panel"] = _filter_records_by_id(
            surfaces.get("right_panel"),
            _id_allow_set(profile, "rightPanelSurfaceIds"),
        )
        surfaces["bottom_drawer"] = _filter_records_by_id(
            surfaces.get("bottom_drawer"),
            _id_allow_set(profile, "bottomDrawerSurfaceIds"),
        )
        capabilities["surfaces"] = surfaces
        capabilities["keybindings"] = _filter_keybindings(
            capabilities.get("keybindings"),
            _id_allow_set(profile, "keybindingCommandIds"),
        )
        for capability_id in _string_items(profile.get("disabledCapabilityIds")):
            current = capabilities.get(capability_id)
            disabled = dict(current or {}) if isinstance(current, dict) else {}
            disabled["enabled"] = False
            capabilities[capability_id] = disabled

    def _agent_capabilities(self) -> Dict[str, Any]:
        current_core = getattr(self._app_host, "current_core", None)
        core = current_core() if callable(current_core) else None
        get_session_capabilities = getattr(core, "get_session_capabilities", None)
        if callable(get_session_capabilities):
            try:
                source = get_session_capabilities("")
            except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
                source = {}
            projected = self._project_agent_capabilities(source)
            if projected:
                return projected
        host_agent_capabilities = getattr(self._app_host, "agent_capabilities", None)
        if not callable(host_agent_capabilities):
            return {}
        try:
            source = host_agent_capabilities()
        except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
            return {}
        return self._project_agent_capabilities(source)

    def _project_agent_capabilities(self, source: Any) -> Dict[str, Any]:
        if not isinstance(source, dict):
            return {}
        projected = {}
        for key in ("agentApplication", "agentApplications", "emptyState"):
            if key in source:
                projected[key] = _safe_mapping(source.get(key))
        return projected

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
