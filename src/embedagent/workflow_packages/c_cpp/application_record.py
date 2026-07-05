from __future__ import annotations

from typing import Any, Dict, List

from embedagent.agent_applications import AgentApplicationRecord
from embedagent.workflow_packages.c_cpp.package_manifest import C_WORKFLOW_PACKAGE_ID


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


def default_c_cpp_agent_application_record(
    default_application_id: str,
    base_app_shell: Dict[str, Any],
) -> AgentApplicationRecord:
    return AgentApplicationRecord(
        application_id=default_application_id,
        label="Default C/C++ Agent",
        profile_id=default_application_id,
        profile_kind="workflow_package",
        workflow_package_ids=(C_WORKFLOW_PACKAGE_ID,),
        builder_path=(
            "embedagent.workflow_packages.c_cpp.application:" "build_c_cpp_agent_application"
        ),
        source_type="builtin",
        source_id="embedagent.workflow_packages.c_cpp",
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
        app_shell=_c_cpp_app_shell(base_app_shell),
    )
