"""Default C/C++ workflow package contracts."""

from embedagent_workflow_cpp.component import cpp_runtime_definition
from embedagent_workflow_cpp.application import cpp_application_manifest, register_application
from embedagent_workflow_cpp.package_manifest import C_WORKFLOW_PACKAGE_ID

__all__ = [
    "C_WORKFLOW_PACKAGE_ID",
    "cpp_application_manifest",
    "cpp_runtime_definition",
    "register_application",
]
