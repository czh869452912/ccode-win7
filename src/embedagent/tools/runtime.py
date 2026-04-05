from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from embedagent.artifacts import ArtifactStore
from embedagent.projection_db import ProjectionDb
from embedagent.tool_result_store import ToolResultStore
from embedagent.modes import allowed_tools_for
from embedagent.session import Observation
from embedagent.tools import build_ops, file_ops, git_ops, shell_ops, todo_ops
from embedagent.tools._base import ToolContext, ToolDefinition, ToolError


@dataclass
class ToolCatalogEntry:
    name: str
    description: str
    permission_category: str
    mode_visibility: List[str]
    workflow_visibility: List[str]
    user_label: str
    progress_renderer_key: str
    result_renderer_key: str
    supports_diff_preview: bool
    context_reducer_key: str
    read_only: bool
    concurrency_safe: bool
    interrupt_behavior: str
    result_budget_policy: str
    activity_kind: str
    context_priority: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "permission_category": self.permission_category,
            "mode_visibility": list(self.mode_visibility),
            "workflow_visibility": list(self.workflow_visibility),
            "user_label": self.user_label,
            "progress_renderer_key": self.progress_renderer_key,
            "result_renderer_key": self.result_renderer_key,
            "supports_diff_preview": self.supports_diff_preview,
            "context_reducer_key": self.context_reducer_key,
            "read_only": self.read_only,
            "concurrency_safe": self.concurrency_safe,
            "interrupt_behavior": self.interrupt_behavior,
            "result_budget_policy": self.result_budget_policy,
            "activity_kind": self.activity_kind,
            "context_priority": self.context_priority,
        }


_DEFAULT_TOOL_METADATA = {
    "read_file": {
        "permission_category": "read",
        "mode_visibility": ["explore", "spec", "code", "debug"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "Read File",
        "progress_renderer_key": "file",
        "result_renderer_key": "file",
        "supports_diff_preview": False,
        "context_reducer_key": "read_file",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "artifact-first",
        "activity_kind": "read",
        "context_priority": 90,
    },
    "list_files": {
        "permission_category": "read",
        "mode_visibility": ["explore", "spec", "code", "debug"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "List Files",
        "progress_renderer_key": "list",
        "result_renderer_key": "list",
        "supports_diff_preview": False,
        "context_reducer_key": "list_files",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "artifact-first",
        "activity_kind": "list",
        "context_priority": 70,
    },
    "search_text": {
        "permission_category": "read",
        "mode_visibility": ["explore", "spec", "code", "debug"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "Search Text",
        "progress_renderer_key": "search",
        "result_renderer_key": "search",
        "supports_diff_preview": False,
        "context_reducer_key": "search_text",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "artifact-first",
        "activity_kind": "search",
        "context_priority": 85,
    },
    "write_file": {
        "permission_category": "workspace_write",
        "mode_visibility": ["spec", "code", "debug"],
        "workflow_visibility": ["chat", "plan", "command"],
        "user_label": "Write File",
        "progress_renderer_key": "file_write",
        "result_renderer_key": "file_write",
        "supports_diff_preview": True,
        "context_reducer_key": "write_file",
        "read_only": False,
        "concurrency_safe": False,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "edit",
        "context_priority": 95,
    },
    "edit_file": {
        "permission_category": "workspace_write",
        "mode_visibility": ["code", "debug"],
        "workflow_visibility": ["chat", "command"],
        "user_label": "Edit File",
        "progress_renderer_key": "file_edit",
        "result_renderer_key": "file_edit",
        "supports_diff_preview": True,
        "context_reducer_key": "edit_file",
        "read_only": False,
        "concurrency_safe": False,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "edit",
        "context_priority": 95,
    },
    "run_command": {
        "permission_category": "shell_exec",
        "mode_visibility": ["debug"],
        "workflow_visibility": ["chat", "command"],
        "user_label": "Run Command",
        "progress_renderer_key": "command",
        "result_renderer_key": "command",
        "supports_diff_preview": False,
        "context_reducer_key": "run_command",
        "read_only": False,
        "concurrency_safe": False,
        "interrupt_behavior": "cancel",
        "result_budget_policy": "artifact-first",
        "activity_kind": "command",
        "context_priority": 88,
    },
    "compile_project": {
        "permission_category": "toolchain_exec",
        "mode_visibility": ["code", "verify"],
        "workflow_visibility": ["chat", "review", "command"],
        "user_label": "Compile Project",
        "progress_renderer_key": "toolchain",
        "result_renderer_key": "toolchain",
        "supports_diff_preview": False,
        "context_reducer_key": "compile_project",
        "read_only": True,
        "concurrency_safe": False,
        "interrupt_behavior": "block",
        "result_budget_policy": "artifact-first",
        "activity_kind": "diagnostic",
        "context_priority": 100,
    },
    "run_tests": {
        "permission_category": "toolchain_exec",
        "mode_visibility": ["verify"],
        "workflow_visibility": ["chat", "review", "command"],
        "user_label": "Run Tests",
        "progress_renderer_key": "toolchain",
        "result_renderer_key": "toolchain",
        "supports_diff_preview": False,
        "context_reducer_key": "run_tests",
        "read_only": True,
        "concurrency_safe": False,
        "interrupt_behavior": "block",
        "result_budget_policy": "artifact-first",
        "activity_kind": "diagnostic",
        "context_priority": 100,
    },
    "run_clang_tidy": {
        "permission_category": "toolchain_exec",
        "mode_visibility": ["verify"],
        "workflow_visibility": ["chat", "review", "command"],
        "user_label": "Run Clang-Tidy",
        "progress_renderer_key": "toolchain",
        "result_renderer_key": "toolchain",
        "supports_diff_preview": False,
        "context_reducer_key": "run_clang_tidy",
        "read_only": True,
        "concurrency_safe": False,
        "interrupt_behavior": "block",
        "result_budget_policy": "artifact-first",
        "activity_kind": "diagnostic",
        "context_priority": 100,
    },
    "run_clang_analyzer": {
        "permission_category": "toolchain_exec",
        "mode_visibility": ["verify"],
        "workflow_visibility": ["chat", "review", "command"],
        "user_label": "Run Clang Analyzer",
        "progress_renderer_key": "toolchain",
        "result_renderer_key": "toolchain",
        "supports_diff_preview": False,
        "context_reducer_key": "run_clang_analyzer",
        "read_only": True,
        "concurrency_safe": False,
        "interrupt_behavior": "block",
        "result_budget_policy": "artifact-first",
        "activity_kind": "diagnostic",
        "context_priority": 100,
    },
    "collect_coverage": {
        "permission_category": "toolchain_exec",
        "mode_visibility": ["verify"],
        "workflow_visibility": ["chat", "review", "command"],
        "user_label": "Collect Coverage",
        "progress_renderer_key": "toolchain",
        "result_renderer_key": "toolchain",
        "supports_diff_preview": False,
        "context_reducer_key": "collect_coverage",
        "read_only": True,
        "concurrency_safe": False,
        "interrupt_behavior": "block",
        "result_budget_policy": "artifact-first",
        "activity_kind": "diagnostic",
        "context_priority": 85,
    },
    "report_quality": {
        "permission_category": "read",
        "mode_visibility": ["verify"],
        "workflow_visibility": ["chat", "review", "command"],
        "user_label": "Quality Report",
        "progress_renderer_key": "quality",
        "result_renderer_key": "quality",
        "supports_diff_preview": False,
        "context_reducer_key": "report_quality",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "diagnostic",
        "context_priority": 85,
    },
    "git_status": {
        "permission_category": "read",
        "mode_visibility": ["explore", "code", "debug"],
        "workflow_visibility": ["chat", "review", "command"],
        "user_label": "Git Status",
        "progress_renderer_key": "git",
        "result_renderer_key": "git",
        "supports_diff_preview": False,
        "context_reducer_key": "git_status",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "git",
        "context_priority": 60,
    },
    "git_diff": {
        "permission_category": "read",
        "mode_visibility": ["explore", "code", "debug"],
        "workflow_visibility": ["chat", "review", "command"],
        "user_label": "Git Diff",
        "progress_renderer_key": "git",
        "result_renderer_key": "git",
        "supports_diff_preview": True,
        "context_reducer_key": "git_diff",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "artifact-first",
        "activity_kind": "git",
        "context_priority": 75,
    },
    "git_log": {
        "permission_category": "read",
        "mode_visibility": ["explore", "code", "debug"],
        "workflow_visibility": ["chat", "review", "command"],
        "user_label": "Git Log",
        "progress_renderer_key": "git",
        "result_renderer_key": "git",
        "supports_diff_preview": False,
        "context_reducer_key": "git_log",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "git",
        "context_priority": 55,
    },
    "manage_todos": {
        "permission_category": "workspace_write",
        "mode_visibility": ["explore", "spec", "code", "debug", "verify"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "Manage Todos",
        "progress_renderer_key": "todos",
        "result_renderer_key": "todos",
        "supports_diff_preview": False,
        "context_reducer_key": "manage_todos",
        "read_only": False,
        "concurrency_safe": False,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "todo",
        "context_priority": 98,
    },
}


class ToolRuntime(object):
    def __init__(self, workspace: str, app_config=None) -> None:
        self.workspace = os.path.realpath(workspace)
        artifact_store = ArtifactStore(self.workspace)
        self.tool_result_store = ToolResultStore(self.workspace)
        self.projection_db = ProjectionDb(
            os.path.join(self.workspace, ".embedagent", "memory", "projections.sqlite3")
        )
        self._ctx = ToolContext(self.workspace, app_config=app_config)
        self.artifact_store = artifact_store  # exposed for external consumers (e.g. InProcessAdapter)
        self.app_config = app_config  # Optional AppConfig; used by loop for path write checking
        all_tools = (
            file_ops.build_tools(self._ctx)
            + shell_ops.build_tools(self._ctx)
            + git_ops.build_tools(self._ctx)
            + build_ops.build_tools(self._ctx)
            + todo_ops.build_tools(self._ctx)
        )
        self._catalog = {}  # type: Dict[str, ToolCatalogEntry]
        self._tools = {td.name: td for td in all_tools}  # type: Dict[str, ToolDefinition]
        for tool in all_tools:
            tool.metadata.update(self._build_default_metadata(tool.name))
            tool.metadata.setdefault("read_only", tool.read_only)
            tool.metadata.setdefault("concurrency_safe", tool.concurrency_safe)
            tool.metadata.setdefault("interrupt_behavior", tool.interrupt_behavior)
            tool.metadata.setdefault("result_budget_policy", tool.result_budget_policy)
            tool.metadata.setdefault("activity_kind", tool.activity_kind)
            tool.metadata.setdefault("context_priority", tool.context_priority)
            self._catalog[tool.name] = ToolCatalogEntry(
                name=tool.name,
                description=tool.description,
                permission_category=str(tool.metadata.get("permission_category") or "read"),
                mode_visibility=list(tool.metadata.get("mode_visibility") or []),
                workflow_visibility=list(tool.metadata.get("workflow_visibility") or []),
                user_label=str(tool.metadata.get("user_label") or tool.name),
                progress_renderer_key=str(tool.metadata.get("progress_renderer_key") or "default"),
                result_renderer_key=str(tool.metadata.get("result_renderer_key") or "default"),
                supports_diff_preview=bool(tool.metadata.get("supports_diff_preview")),
                context_reducer_key=str(tool.metadata.get("context_reducer_key") or tool.name),
                read_only=bool(tool.metadata.get("read_only")),
                concurrency_safe=bool(tool.metadata.get("concurrency_safe")),
                interrupt_behavior=str(tool.metadata.get("interrupt_behavior") or "block"),
                result_budget_policy=str(tool.metadata.get("result_budget_policy") or "default"),
                activity_kind=str(tool.metadata.get("activity_kind") or "tool"),
                context_priority=int(tool.metadata.get("context_priority") or 50),
            )

    def schemas(self) -> List[Dict[str, Any]]:
        return [td.schema() for td in self._tools.values()]

    def schemas_for(
        self,
        mode_name: str,
        workflow_state: str = "chat",
        tool_names: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        allowed_by_mode = set(tool_names or allowed_tools_for(mode_name))
        schemas = []
        for name, tool in self._tools.items():
            if name not in allowed_by_mode:
                continue
            entry = self._catalog.get(name)
            if entry is not None and entry.workflow_visibility:
                if workflow_state not in entry.workflow_visibility and "any" not in entry.workflow_visibility:
                    continue
            schemas.append(tool.schema())
        return schemas

    def catalog_entries(self) -> List[Dict[str, Any]]:
        return [entry.to_dict() for entry in self._catalog.values()]

    def tool_catalog_entry(self, name: str) -> Optional[Dict[str, Any]]:
        entry = self._catalog.get(name)
        return entry.to_dict() if entry is not None else None

    def tool_capabilities(self, name: str) -> Dict[str, Any]:
        entry = self._catalog.get(name)
        return entry.to_dict() if entry is not None else {}

    def runtime_environment_snapshot(self) -> Dict[str, Any]:
        return self._ctx.runtime_environment_snapshot()

    def workspace_recipes(self) -> Dict[str, Any]:
        return self._ctx.list_workspace_recipes()

    def execute(self, name: str, arguments: Dict[str, Any]) -> Observation:
        return self.execute_with_interrupt(name, arguments, None)

    def execute_with_interrupt(
        self,
        name: str,
        arguments: Dict[str, Any],
        stop_event=None,
    ) -> Observation:
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
        observation.tool_name = name
        if isinstance(observation.data, dict):
            entry = self._catalog.get(name)
            if entry is not None:
                data = dict(observation.data)
                data.setdefault("tool_label", entry.user_label)
                data.setdefault("permission_category", entry.permission_category)
                data.setdefault("supports_diff_preview", entry.supports_diff_preview)
                data.setdefault("progress_renderer_key", entry.progress_renderer_key)
                data.setdefault("result_renderer_key", entry.result_renderer_key)
                observation.data = data
        return observation

    def _build_default_metadata(self, name: str) -> Dict[str, Any]:
        default = _DEFAULT_TOOL_METADATA.get(name, {})
        if default:
            return dict(default)
        return {
            "permission_category": "read",
            "mode_visibility": ["explore", "spec", "code", "debug", "verify"],
            "workflow_visibility": ["chat", "plan", "review", "command"],
            "user_label": name,
            "progress_renderer_key": "default",
            "result_renderer_key": "default",
            "supports_diff_preview": False,
            "context_reducer_key": name,
            "read_only": False,
            "concurrency_safe": False,
            "interrupt_behavior": "block",
            "result_budget_policy": "default",
            "activity_kind": "tool",
            "context_priority": 50,
        }
