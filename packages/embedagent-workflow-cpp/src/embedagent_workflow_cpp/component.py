from __future__ import annotations

from embedagent_core import ApplicationRuntimePolicy, RuntimeDefinition
from embedagent_core.profile_runtime import (
    AgentProfileRuntimePolicy,
    AgentProfileToolPolicy,
    AgentProfileWritePathPolicy,
)

from embedagent_workflow_cpp.extension import CHarnessWorkflowExtension
from embedagent_workflow_cpp.profile import default_cpp_profile


def cpp_runtime_definition() -> RuntimeDefinition:
    profile = default_cpp_profile()
    return RuntimeDefinition(
        agent_id="embedagent.default_c_cpp",
        workflow_state="",
        extensions=(CHarnessWorkflowExtension(),),
        application_policy=ApplicationRuntimePolicy(
            default_mode=profile.default_mode,
            mode_tool_policy=AgentProfileToolPolicy(profile),
            write_path_policy=AgentProfileWritePathPolicy(profile),
            mode_runtime_policy=AgentProfileRuntimePolicy(profile),
        ),
    )
