from __future__ import annotations

from typing import Any, Dict, List

from embedagent.workflow_package_manifest import (
    WorkflowPackageManifest,
    WorkflowPackDeclaration,
    WorkflowToolDeclaration,
)
from embedagent.workflow_packages.c_cpp.packs import C_WORKFLOW_PACKS
from embedagent.workflow_packages.c_cpp.tool_metadata import C_WORKFLOW_TOOL_METADATA

C_WORKFLOW_PACKAGE_ID = "embedagent.c_workflow"
C_WORKFLOW_PACKAGE_LABEL = "C/C++ Workflow"
C_WORKFLOW_PACKAGE_SOURCE_ID = "embedagent.workflow_packages.c_cpp"
C_WORKFLOW_SUPPORTED_MODES = ["build", "debug", "verify"]
C_WORKFLOW_SUPPORTED_STATES = ["chat", "plan", "review", "command"]
C_WORKFLOW_RESOURCE_SCOPES = [".embedagent/recipes"]


def _tool_declarations() -> List[WorkflowToolDeclaration]:
    declarations = []
    for name, metadata in sorted(C_WORKFLOW_TOOL_METADATA.items()):
        safe_metadata = dict(metadata or {})
        declarations.append(
            WorkflowToolDeclaration(
                name=name,
                permission_category=str(safe_metadata.get("permission_category") or "other"),
                source_type="workflow_package",
                source_id=C_WORKFLOW_PACKAGE_SOURCE_ID,
                metadata=safe_metadata,
            )
        )
    return declarations


def _pack_declarations() -> List[WorkflowPackDeclaration]:
    return [
        WorkflowPackDeclaration(name=name, tool_names=list(tool_names or []))
        for name, tool_names in sorted(C_WORKFLOW_PACKS.items())
    ]


def build_c_workflow_package_manifest() -> WorkflowPackageManifest:
    return WorkflowPackageManifest(
        package_id=C_WORKFLOW_PACKAGE_ID,
        label=C_WORKFLOW_PACKAGE_LABEL,
        version="1",
        source_type="builtin",
        source_id=C_WORKFLOW_PACKAGE_SOURCE_ID,
        supported_modes=list(C_WORKFLOW_SUPPORTED_MODES),
        supported_workflow_states=list(C_WORKFLOW_SUPPORTED_STATES),
        tools=_tool_declarations(),
        packs=_pack_declarations(),
        resource_scopes=list(C_WORKFLOW_RESOURCE_SCOPES),
    )


def c_workflow_package_manifest_dict() -> Dict[str, Any]:
    return build_c_workflow_package_manifest().to_dict()
