from __future__ import annotations

from typing import List

from embedagent_workflow_cpp import recipe_ops, session_ops
from embedagent_workflow_cpp.tool_metadata import C_WORKFLOW_TOOL_METADATA


def _attach_metadata(tool):
    metadata = dict(C_WORKFLOW_TOOL_METADATA.get(tool.name, {}) or {})
    if metadata:
        tool.metadata.update(metadata)
    return tool


def build_c_workflow_tools(ctx) -> List[object]:
    definitions = []
    definitions.extend(recipe_ops.build_tools(ctx))
    definitions.extend(session_ops.build_workflow_tools(ctx))
    return [_attach_metadata(tool) for tool in definitions]
