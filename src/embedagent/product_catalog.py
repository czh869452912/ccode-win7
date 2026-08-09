from __future__ import annotations

from typing import Iterable, Optional, Tuple

from embedagent_host.runtime.agent_applications import (
    BUILTIN_AGENT_APPLICATION_RECORDS,
    AgentApplicationRecord,
    AgentApplicationRegistry,
)
from embedagent_workflow_cpp.component import cpp_runtime_definition
from embedagent_workflow_cpp.package_manifest import C_WORKFLOW_PACKAGE_ID
from embedagent_workflow_cpp.profile import default_cpp_profile
from embedagent_workflow_cpp.workspace_profile import c_cpp_workspace_profile_detectors

from embedagent.frontend.shell.defaults import (
    cpp_workflow_contribution,
    desktop_file_contribution,
    minimal_shell_contribution,
    preview_contribution,
    source_control_contribution,
    terminal_contribution,
)
from embedagent.frontend.shell.registration import ShellContribution, ShellContributionRegistry

DEFAULT_C_CPP_AGENT_APPLICATION_ID = "embedagent.default_c_cpp"


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
    )


def product_agent_application_registry(
    allowed_application_ids: Optional[Tuple[str, ...]] = None,
) -> AgentApplicationRegistry:
    records = (default_c_cpp_application_record(),) + tuple(BUILTIN_AGENT_APPLICATION_RECORDS)
    if allowed_application_ids is None:
        return AgentApplicationRegistry(
            application_records=records,
            default_application_id=DEFAULT_C_CPP_AGENT_APPLICATION_ID,
        )

    allowed = tuple(str(item or "").strip() for item in allowed_application_ids)
    known_ids = tuple(record.application_id for record in records)
    if not allowed or any(not item for item in allowed) or len(allowed) != len(set(allowed)):
        raise ValueError("Allowed agent applications must contain unique nonempty ids")
    unknown = tuple(item for item in allowed if item not in known_ids)
    if unknown:
        raise ValueError("Unknown allowed agent application %r" % (unknown[0],))
    selected = tuple(record for record in records if record.application_id in allowed)
    if not selected:
        raise ValueError("Allowed agent applications did not select a product application")
    return AgentApplicationRegistry(
        application_records=selected,
        default_application_id=allowed[0],
    )


def _merge_shell_contributions(
    contributions: Iterable[ShellContribution],
) -> ShellContribution:
    records = tuple(contributions)
    return ShellContribution(
        commands=tuple(item for record in records for item in record.commands),
        surfaces=tuple(item for record in records for item in record.surfaces),
        keybindings=tuple(item for record in records for item in record.keybindings),
        tool_presentations=tuple(item for record in records for item in record.tool_presentations),
        timeline_items=tuple(item for record in records for item in record.timeline_items),
        interactions=tuple(item for record in records for item in record.interactions),
    )


def product_shell_registry() -> ShellContributionRegistry:
    generic = _merge_shell_contributions(
        (
            minimal_shell_contribution(),
            desktop_file_contribution(),
            terminal_contribution(),
            source_control_contribution(),
            preview_contribution(),
        )
    )
    applications = dict(
        (record.application_id, ShellContribution()) for record in BUILTIN_AGENT_APPLICATION_RECORDS
    )
    applications[DEFAULT_C_CPP_AGENT_APPLICATION_ID] = cpp_workflow_contribution()
    return ShellContributionRegistry(generic=generic, applications=applications)


def product_shell_compiler():
    registry = product_shell_registry()

    def compile_descriptor(application_id, session_capabilities):
        return registry.compile(application_id, session_capabilities)

    return compile_descriptor
