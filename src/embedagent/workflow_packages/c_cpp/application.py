from __future__ import annotations

from typing import Any

from embedagent.agent_applications import (
    DEFAULT_AGENT_APPLICATION_ID,
    AgentApplication,
    AgentApplicationManifest,
)
from embedagent.workflow_packages.c_cpp.agent_profile import default_c_cpp_agent_profile
from embedagent.workflow_packages.c_cpp.extension import CHarnessWorkflowExtension
from embedagent.workflow_packages.c_cpp.package_manifest import C_WORKFLOW_PACKAGE_ID
from embedagent.workflow_packages.c_cpp.workspace_profile import (
    c_cpp_workspace_profile_detectors,
)
from embedagent_core.extensions import ExtensionManager


def c_cpp_agent_application_manifest() -> AgentApplicationManifest:
    return AgentApplicationManifest(
        application_id=DEFAULT_AGENT_APPLICATION_ID,
        label="Default C/C++ Agent",
        profile_id="embedagent.default_c_cpp",
        workflow_package_ids=(C_WORKFLOW_PACKAGE_ID,),
        source_type="builtin",
        source_id="embedagent.workflow_packages.c_cpp",
        default=True,
    )


def build_c_cpp_agent_application(tools: Any) -> AgentApplication:
    workflow_extension = CHarnessWorkflowExtension(tools=tools)
    return AgentApplication(
        application_id=DEFAULT_AGENT_APPLICATION_ID,
        label="Default C/C++ Agent",
        profile=default_c_cpp_agent_profile(),
        extension_manager=ExtensionManager([workflow_extension]),
        manifest=c_cpp_agent_application_manifest(),
        workflow_refreshers=(workflow_extension,),
        workspace_profile_detectors=c_cpp_workspace_profile_detectors(),
    )
