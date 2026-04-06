from __future__ import annotations

from embedagent.tooling.packs import pack_tool_names
from embedagent.tools._base import ToolContext
from embedagent.tools_v2 import discovery_ops, edit_ops, read_ops, recipe_ops, session_ops


class ToolRuntimeV2(object):
    def __init__(self, workspace, app_config=None):
        self.workspace = workspace
        self._ctx = ToolContext(workspace, app_config=app_config)
        definitions = []
        definitions.extend(discovery_ops.build_tools(self._ctx))
        definitions.extend(read_ops.build_tools(self._ctx))
        definitions.extend(edit_ops.build_tools(self._ctx))
        definitions.extend(recipe_ops.build_tools(self._ctx))
        definitions.extend(session_ops.build_tools(self._ctx))
        self._tools = dict((tool.name, tool) for tool in definitions)

    def schemas_for_pack(self, pack_name):
        allowed = set(pack_tool_names(pack_name))
        return [
            tool.schema()
            for name, tool in self._tools.items()
            if name in allowed
        ]

    def execute(self, name, arguments):
        return self._tools[name].handler(arguments)
