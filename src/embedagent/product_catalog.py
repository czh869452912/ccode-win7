from __future__ import annotations

from typing import Any, Dict, List

from embedagent_host.runtime.agent_applications import (
    BUILTIN_AGENT_APPLICATION_RECORDS,
    AgentApplicationRecord,
    AgentApplicationRegistry,
)
from embedagent_workflow_cpp.component import cpp_runtime_definition
from embedagent_workflow_cpp.package_manifest import C_WORKFLOW_PACKAGE_ID
from embedagent_workflow_cpp.profile import default_cpp_profile
from embedagent_workflow_cpp.workspace_profile import c_cpp_workspace_profile_detectors

DEFAULT_C_CPP_AGENT_APPLICATION_ID = "embedagent.default_c_cpp"

_DEFAULT_C_CPP_APP_SHELL = {
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


def _command_palette_groups_with_workflow(base_groups: Any) -> List[str]:
    groups = [str(item) for item in list(base_groups or []) if str(item or "").strip()]
    if "workflow" in groups:
        return groups
    if "view" in groups:
        index = groups.index("view")
        return groups[:index] + ["workflow"] + groups[index:]
    return groups + ["workflow"]


def _c_cpp_app_shell(base_app_shell: Dict[str, Any]) -> Dict[str, Any]:
    app_shell = dict(base_app_shell or {})
    app_shell["commandPaletteGroupIds"] = tuple(
        _command_palette_groups_with_workflow(app_shell.get("commandPaletteGroupIds"))
    )
    return app_shell


def default_c_cpp_application_record() -> AgentApplicationRecord:
    return AgentApplicationRecord(
        application_id=DEFAULT_C_CPP_AGENT_APPLICATION_ID,
        label="Default C/C++ Agent",
        profile_id="embedagent.default_c_cpp",
        profile_factory=default_cpp_profile,
        runtime_factory=cpp_runtime_definition,
        workflow_package_ids=(C_WORKFLOW_PACKAGE_ID,),
        workspace_profile_detectors_factory=c_cpp_workspace_profile_detectors,
        source_type="builtin",
        source_id="embedagent_workflow_cpp",
        default=True,
        empty_state={
            "scenario_label": "C/C++ workspace",
            "primary": "Open a C/C++ project",
            "secondary": (
                "The selected agent will load its Clang-centered workflow after "
                "workspace activation."
            ),
            "path_placeholder": "Path to C/C++ project",
        },
        app_shell=_c_cpp_app_shell(_DEFAULT_C_CPP_APP_SHELL),
    )


def product_agent_application_registry() -> AgentApplicationRegistry:
    return AgentApplicationRegistry(
        application_records=(default_c_cpp_application_record(),)
        + tuple(BUILTIN_AGENT_APPLICATION_RECORDS),
        default_application_id=DEFAULT_C_CPP_AGENT_APPLICATION_ID,
    )
