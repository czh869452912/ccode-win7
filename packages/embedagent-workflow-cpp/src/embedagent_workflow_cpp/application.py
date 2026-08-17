"""Standalone C/C++ application plugin registration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple

from embedagent_core import ApplicationRuntimeContribution


@dataclass(frozen=True)
class CppApplicationManifest:
    application_id: str = "embedagent.default_c_cpp"
    version: str = "0.1.0"
    api_version: str = "agent_application_v1"
    distribution_id: str = "embedagent-workflow-cpp"
    registration_entry: str = "embedagent_workflow_cpp.application:register_application"
    requires: Tuple[str, ...] = ("embedagent-core", "embedagent-protocol")
    capabilities: Tuple[str, ...] = (
        "mode.explore",
        "mode.spec",
        "mode.build",
        "mode.debug",
        "mode.verify",
    )
    runtime_requirements: Tuple[str, ...] = ("runtime.python", "toolchain.clang", "symbols.ctags")

    def to_dict(self):
        return {
            "application_id": self.application_id,
            "version": self.version,
            "api_version": self.api_version,
            "distribution_id": self.distribution_id,
            "registration_entry": self.registration_entry,
            "requires": list(self.requires),
            "capabilities": list(self.capabilities),
            "runtime_requirements": list(self.runtime_requirements),
        }


def cpp_application_manifest() -> CppApplicationManifest:
    return CppApplicationManifest()


def _shell_contribution() -> Any:
    from embedagent_protocol import CommandDescriptor

    class Contribution(object):
        commands = tuple(
            CommandDescriptor(
                id=command_id,
                label=label,
                group="workflow",
                dispatch={"kind": "session.command", "command": capability},
                availability={"capability_id": capability, "visible_when": "has_session"},
                source_type="application",
                source_id="embedagent.workflow.cpp",
            )
            for command_id, label, capability in (
                ("workflow.run", "Run Recipe", "run"),
                ("workflow.review", "Review", "review"),
                ("workflow.recipes", "List Recipes", "recipes"),
                ("workflow.diff", "View Diff", "diff"),
                ("workflow.tasks", "View Tasks", "tasks"),
            )
        )
        surfaces = ()
        keybindings = ()
        tool_presentations = ()
        timeline_items = ()
        interactions = ()

    return Contribution()


def register_application(registrar: Any):
    """Register C/C++ runtime and shell capabilities into the generic host."""
    from embedagent_workflow_cpp.component import cpp_runtime_definition
    from embedagent_workflow_cpp.profile import default_cpp_profile
    from embedagent_workflow_cpp.workspace_profile import c_cpp_workspace_profile_detectors

    source_id = "embedagent.workflow.cpp"
    disposers = []
    disposers.append(
        registrar.add_runtime_contribution(
            ApplicationRuntimeContribution(
                application_id="embedagent.default_c_cpp",
                label="Default C/C++ Agent",
                runtime_definition_factory=cpp_runtime_definition,
                workspace_contribution_factory=c_cpp_workspace_profile_detectors,
                capabilities=tuple(cpp_application_manifest().capabilities),
                empty_state={
                    "scenario_label": "C/C++ workspace",
                    "primary": "Open a C/C++ project",
                    "secondary": "The selected agent will load its Clang-centered workflow after workspace activation.",
                    "path_placeholder": "Path to C/C++ project",
                },
                metadata={"domain": "cpp", "source_id": source_id},
            ),
            source_id,
        )
    )
    runtime_definition = cpp_runtime_definition()
    for extension in tuple(runtime_definition.extensions or ()):
        disposers.append(registrar.add_extension(extension, source_id))
    disposers.append(registrar.add_prompt_provider(default_cpp_profile, source_id))
    disposers.append(registrar.add_context_provider(c_cpp_workspace_profile_detectors, source_id))
    disposers.append(registrar.add_shell_contribution(_shell_contribution(), source_id))

    def dispose() -> None:
        for disposer in reversed(disposers):
            disposer()

    return dispose
