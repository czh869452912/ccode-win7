from __future__ import annotations

import os
from typing import Any, Dict, List

from embedagent.artifacts import ArtifactStore
from embedagent.session import Observation
from embedagent.tools import build_ops, file_ops, git_ops, shell_ops, todo_ops
from embedagent.tools._base import ToolContext, ToolDefinition, ToolError


class ToolRuntime(object):
    def __init__(self, workspace: str, app_config=None) -> None:
        self.workspace = os.path.realpath(workspace)
        artifact_store = ArtifactStore(self.workspace)
        self._ctx = ToolContext(self.workspace, artifact_store)
        self.artifact_store = artifact_store  # exposed for external consumers (e.g. InProcessAdapter)
        self.app_config = app_config  # Optional AppConfig; used by loop for path write checking
        all_tools = (
            file_ops.build_tools(self._ctx)
            + shell_ops.build_tools(self._ctx)
            + git_ops.build_tools(self._ctx)
            + build_ops.build_tools(self._ctx)
            + todo_ops.build_tools(self._ctx)
        )
        self._tools = {td.name: td for td in all_tools}  # type: Dict[str, ToolDefinition]

    def schemas(self) -> List[Dict[str, Any]]:
        return [td.schema() for td in self._tools.values()]

    def execute(self, name: str, arguments: Dict[str, Any]) -> Observation:
        tool = self._tools.get(name)
        if tool is None:
            return Observation(
                tool_name=name,
                success=False,
                error="未找到对应工具。",
                data={},
            )
        try:
            if not isinstance(arguments, dict):
                raise ToolError("工具参数必须是对象。")
            observation = self._ctx.shrink_observation(tool.handler(arguments))
        except ToolError as exc:
            return Observation(
                tool_name=name,
                success=False,
                error=str(exc),
                data={},
            )
        except Exception as exc:
            return Observation(
                tool_name=name,
                success=False,
                error="工具执行失败：%s" % exc,
                data={},
            )
        observation.tool_name = name
        return observation
