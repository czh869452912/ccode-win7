from __future__ import annotations

from embedagent.session import Observation
from embedagent.tooling.packs import pack_tool_names
from embedagent.tools._base import ToolContext, ToolError
from embedagent.tools_v2 import discovery_ops, edit_ops, read_ops, recipe_ops, session_ops


_DEFAULT_TOOL_METADATA = {
    "read_file": {"permission_category": "read", "read_only": True, "concurrency_safe": True},
    "list_dir": {"permission_category": "read", "read_only": True, "concurrency_safe": True},
    "glob_files": {"permission_category": "read", "read_only": True, "concurrency_safe": True},
    "grep_text": {"permission_category": "read", "read_only": True, "concurrency_safe": True},
    "edit_file": {"permission_category": "workspace_write", "read_only": False, "concurrency_safe": False},
    "write_file": {"permission_category": "workspace_write", "read_only": False, "concurrency_safe": False},
    "list_recipes": {"permission_category": "read", "read_only": True, "concurrency_safe": True},
    "run_recipe": {"permission_category": "toolchain_exec", "read_only": False, "concurrency_safe": False},
    "report_quality_v2": {"permission_category": "read", "read_only": True, "concurrency_safe": True},
    "task_status": {"permission_category": "read", "read_only": True, "concurrency_safe": True},
    "ask_user": {"permission_category": "read", "read_only": True, "concurrency_safe": True},
    "record_failing_evidence": {"permission_category": "read", "read_only": True, "concurrency_safe": True},
}


class ToolRuntimeV2(object):
    def __init__(self, workspace, app_config=None):
        self.workspace = workspace
        self.app_config = app_config
        self._ctx = ToolContext(workspace, app_config=app_config)
        definitions = []
        definitions.extend(discovery_ops.build_tools(self._ctx))
        definitions.extend(read_ops.build_tools(self._ctx))
        definitions.extend(edit_ops.build_tools(self._ctx))
        definitions.extend(recipe_ops.build_tools(self._ctx))
        definitions.extend(session_ops.build_tools(self._ctx))
        self._tools = dict((tool.name, tool) for tool in definitions)

    def has_tool(self, name):
        return str(name or "") in self._tools

    def schemas(self):
        return [tool.schema() for tool in self._tools.values()]

    def schemas_for_pack(self, pack_name, names_only=False):
        allowed = set(pack_tool_names(pack_name))
        if names_only:
            return [name for name in self._tools if name in allowed]
        return [
            tool.schema()
            for name, tool in self._tools.items()
            if name in allowed
        ]

    def tool_capabilities(self, name):
        default = dict(_DEFAULT_TOOL_METADATA.get(str(name or ""), {}))
        default.setdefault("name", str(name or ""))
        default.setdefault("user_label", str(name or ""))
        return default

    def tool_catalog_entry(self, name):
        return self.tool_capabilities(name)

    def execute(self, name, arguments):
        return self.execute_with_interrupt(name, arguments, None)

    def execute_with_interrupt(self, name, arguments, stop_event=None):
        tool = self._tools.get(name)
        if tool is None:
            return Observation(tool_name=name, success=False, error="未找到对应工具。", data={})
        try:
            if not isinstance(arguments, dict):
                raise ToolError("工具参数必须是对象。")
            self._ctx.set_interrupt_event(stop_event)
            observation = tool.handler(arguments)
        except ToolError as exc:
            return Observation(
                tool_name=name,
                success=False,
                error=str(exc),
                data={"error_kind": "tool_error", "retryable": True},
            )
        except Exception as exc:
            return Observation(
                tool_name=name,
                success=False,
                error="工具执行失败：%s" % exc,
                data={"error_kind": "tool_error", "retryable": True},
            )
        finally:
            self._ctx.clear_interrupt_event()
        if isinstance(observation.data, dict):
            data = dict(observation.data)
            metadata = self.tool_capabilities(name)
            data.setdefault("tool_label", metadata.get("user_label") or name)
            data.setdefault("permission_category", metadata.get("permission_category") or "read")
            observation.data = data
        observation.tool_name = name
        return observation
