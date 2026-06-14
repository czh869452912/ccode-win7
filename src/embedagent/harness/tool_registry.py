from __future__ import annotations

from typing import List

from embedagent.tools import recipe_ops, session_ops


def build_c_workflow_tools(ctx) -> List[object]:
    definitions = []
    definitions.extend(recipe_ops.build_tools(ctx))
    definitions.extend(session_ops.build_tools(ctx))
    return definitions
