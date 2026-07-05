from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from embedagent.agent_profiles import (
    AgentProfile,
    generic_agent_profile,
    html_agent_profile,
    python_agent_profile,
)
from embedagent_core.extensions import ExtensionManager

DEFAULT_AGENT_APPLICATION_ID = "embedagent.default_c_cpp"
GENERIC_AGENT_APPLICATION_ID = "embedagent.generic"
PYTHON_AGENT_APPLICATION_ID = "embedagent.python"
HTML_AGENT_APPLICATION_ID = "embedagent.html"


@dataclass(frozen=True)
class AgentApplicationManifest:
    application_id: str
    label: str
    profile_id: str
    workflow_package_ids: Tuple[str, ...] = field(default_factory=tuple)
    source_type: str = "builtin"
    source_id: str = ""
    default: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "applicationId": self.application_id,
            "label": self.label,
            "profileId": self.profile_id,
            "workflowPackageIds": list(self.workflow_package_ids),
            "sourceType": self.source_type,
            "sourceId": self.source_id,
            "default": bool(self.default),
            "metadata": dict(self.metadata),
        }


@dataclass
class AgentApplication:
    application_id: str
    label: str
    profile: AgentProfile
    extension_manager: ExtensionManager
    manifest: Optional[AgentApplicationManifest] = None
    workflow_refreshers: Tuple[Any, ...] = field(default_factory=tuple)
    workspace_profile_detectors: Tuple[Any, ...] = field(default_factory=tuple)

    def refresh_managed_session(
        self,
        state: Any,
        workspace: str,
        observations: Any = None,
    ) -> None:
        for refresher in self.workflow_refreshers:
            refresh = getattr(refresher, "refresh_managed_session", None)
            if callable(refresh):
                refresh(state, workspace, observations=observations)


@dataclass(frozen=True)
class AgentApplicationRecord:
    application_id: str
    label: str
    profile_id: str
    profile_kind: str
    workflow_package_ids: Tuple[str, ...] = field(default_factory=tuple)
    builder_path: str = ""
    source_type: str = "builtin"
    source_id: str = ""
    default: bool = False
    empty_state: Dict[str, Any] = field(default_factory=dict)
    app_shell: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_manifest(self) -> AgentApplicationManifest:
        metadata = dict(self.metadata or {})
        if self.app_shell:
            metadata["appShell"] = _copy_value(self.app_shell)
        return AgentApplicationManifest(
            application_id=self.application_id,
            label=self.label,
            profile_id=self.profile_id,
            workflow_package_ids=tuple(self.workflow_package_ids),
            source_type=self.source_type,
            source_id=self.source_id,
            default=bool(self.default),
            metadata=metadata,
        )


_BASE_APP_SHELL = {
    "rightPanelSurfaceIds": (
        "files",
        "file",
        "terminal",
        "plan",
        "settings",
        "diagnostics",
    ),
    "bottomDrawerSurfaceIds": ("run_output", "terminal"),
    "appCommandIds": ("app.settings", "app.diagnostics", "app.reload"),
    "keybindingCommandIds": (
        "palette.open",
        "palette.close",
        "message.stop",
        "view.toggle_right_panel",
        "app.settings",
        "view.toggle_bottom_drawer",
        "surface.files",
        "surface.terminal",
        "message.send",
    ),
    "commandPaletteGroupIds": (
        "app",
        "session",
        "message",
        "mode",
        "surface",
        "workspace",
        "view",
    ),
    "disabledCapabilityIds": ("source_control", "preview"),
}

_CODE_APP_SHELL = {
    "rightPanelSurfaceIds": (
        "files",
        "file",
        "terminal",
        "diff",
        "plan",
        "source_control",
        "settings",
        "diagnostics",
    ),
    "bottomDrawerSurfaceIds": ("run_output", "terminal"),
    "appCommandIds": (
        "app.settings",
        "app.diagnostics",
        "app.source_control",
        "app.reload",
    ),
    "keybindingCommandIds": (
        "palette.open",
        "palette.close",
        "message.stop",
        "view.toggle_right_panel",
        "app.settings",
        "view.toggle_bottom_drawer",
        "surface.files",
        "surface.terminal",
        "surface.diff",
        "message.send",
    ),
    "commandPaletteGroupIds": (
        "app",
        "session",
        "message",
        "mode",
        "surface",
        "workspace",
        "view",
    ),
    "disabledCapabilityIds": ("preview",),
}

_WEB_APP_SHELL = {
    "rightPanelSurfaceIds": (
        "preview",
        "files",
        "file",
        "terminal",
        "diff",
        "plan",
        "source_control",
        "settings",
        "diagnostics",
    ),
    "bottomDrawerSurfaceIds": ("run_output", "terminal"),
    "appCommandIds": (
        "app.settings",
        "app.diagnostics",
        "app.source_control",
        "app.reload",
    ),
    "keybindingCommandIds": (
        "palette.open",
        "palette.close",
        "message.stop",
        "view.toggle_right_panel",
        "app.settings",
        "view.toggle_bottom_drawer",
        "surface.files",
        "surface.terminal",
        "surface.diff",
        "surface.preview",
        "message.send",
    ),
    "commandPaletteGroupIds": (
        "app",
        "session",
        "message",
        "mode",
        "surface",
        "workspace",
        "view",
    ),
    "disabledCapabilityIds": (),
}


def _default_c_cpp_application_record() -> AgentApplicationRecord:
    from embedagent.workflow_packages.c_cpp.application_record import (
        default_c_cpp_agent_application_record,
    )

    return default_c_cpp_agent_application_record(DEFAULT_AGENT_APPLICATION_ID, _WEB_APP_SHELL)


BUILTIN_AGENT_APPLICATION_RECORDS = (
    _default_c_cpp_application_record(),
    AgentApplicationRecord(
        application_id=GENERIC_AGENT_APPLICATION_ID,
        label="Generic Agent",
        profile_id=GENERIC_AGENT_APPLICATION_ID,
        profile_kind="generic",
        source_type="builtin",
        source_id="embedagent.agent_profiles",
        empty_state={
            "scenario_label": "Generic workspace",
            "primary": "Open a local project",
            "secondary": "The selected agent will use generic project modes after workspace activation.",
            "path_placeholder": "Path to project",
        },
        app_shell=_BASE_APP_SHELL,
        metadata={"domain": "generic"},
    ),
    AgentApplicationRecord(
        application_id=PYTHON_AGENT_APPLICATION_ID,
        label="Python Agent",
        profile_id=PYTHON_AGENT_APPLICATION_ID,
        profile_kind="python",
        source_type="builtin",
        source_id="embedagent.agent_profiles",
        empty_state={
            "scenario_label": "Python workspace",
            "primary": "Open a Python project",
            "secondary": "The selected agent will use Python project modes after workspace activation.",
            "path_placeholder": "Path to Python project",
        },
        app_shell=_CODE_APP_SHELL,
        metadata={"domain": "python"},
    ),
    AgentApplicationRecord(
        application_id=HTML_AGENT_APPLICATION_ID,
        label="HTML Agent",
        profile_id=HTML_AGENT_APPLICATION_ID,
        profile_kind="html",
        source_type="builtin",
        source_id="embedagent.agent_profiles",
        empty_state={
            "scenario_label": "HTML/Web workspace",
            "primary": "Open an HTML/Web project",
            "secondary": "The selected agent will use frontend project modes after workspace activation.",
            "path_placeholder": "Path to HTML/Web project",
        },
        app_shell=_WEB_APP_SHELL,
        metadata={"domain": "html"},
    ),
)


def _record_by_id(application_id: str) -> AgentApplicationRecord:
    requested = str(application_id or "").strip() or DEFAULT_AGENT_APPLICATION_ID
    for record in BUILTIN_AGENT_APPLICATION_RECORDS:
        if requested == record.application_id:
            return record
    raise ValueError("Unknown agent application %r" % (application_id,))


def _profile_for_record(record: AgentApplicationRecord) -> AgentProfile:
    if record.profile_kind == "generic":
        return generic_agent_profile()
    if record.profile_kind == "python":
        return python_agent_profile()
    if record.profile_kind == "html":
        return html_agent_profile()
    raise ValueError("Unknown agent profile kind %r" % (record.profile_kind,))


def _build_profile_application(
    record: AgentApplicationRecord,
    profile: AgentProfile,
) -> AgentApplication:
    manifest = record.to_manifest()
    return AgentApplication(
        application_id=manifest.application_id,
        label=manifest.label,
        profile=profile,
        extension_manager=ExtensionManager(),
        manifest=manifest,
    )


def _load_application_builder(path: str) -> Any:
    module_name, separator, function_name = str(path or "").partition(":")
    if not module_name or separator != ":" or not function_name:
        raise ValueError("Invalid agent application builder path %r" % (path,))
    module = importlib.import_module(module_name)
    builder = getattr(module, function_name, None)
    if not callable(builder):
        raise ValueError("Agent application builder is not callable: %s" % (path,))
    return builder


def generic_agent_application_manifest() -> AgentApplicationManifest:
    return _record_by_id(GENERIC_AGENT_APPLICATION_ID).to_manifest()


def python_agent_application_manifest() -> AgentApplicationManifest:
    return _record_by_id(PYTHON_AGENT_APPLICATION_ID).to_manifest()


def html_agent_application_manifest() -> AgentApplicationManifest:
    return _record_by_id(HTML_AGENT_APPLICATION_ID).to_manifest()


def available_agent_application_manifests() -> List[AgentApplicationManifest]:
    return [record.to_manifest() for record in BUILTIN_AGENT_APPLICATION_RECORDS]


def _copy_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _copy_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy_value(item) for item in value]
    return value


def _application_descriptor_payload(
    record: AgentApplicationRecord,
    active: bool = False,
) -> Dict[str, Any]:
    payload = record.to_manifest().to_dict()
    payload["active"] = bool(active)
    return payload


def agent_application_capability_payload(application_id: str = "") -> Dict[str, Any]:
    selected = _record_by_id(application_id)
    selected_id = selected.application_id
    return {
        "agentApplication": _application_descriptor_payload(selected, active=True),
        "agentApplications": [
            _application_descriptor_payload(
                record,
                active=record.application_id == selected_id,
            )
            for record in BUILTIN_AGENT_APPLICATION_RECORDS
        ],
        "emptyState": _copy_value(selected.empty_state),
    }


def build_agent_application(application_id: str, tools: Any) -> AgentApplication:
    record = _record_by_id(application_id)
    if record.builder_path:
        return _load_application_builder(record.builder_path)(tools)
    return _build_profile_application(record, _profile_for_record(record))
