from __future__ import annotations  # noqa: I001

import os
import re
from typing import Any, Dict, List, Optional

from embedagent_core.capabilities import (
    resource_capability_descriptors,
    runtime_tool_capability_descriptors,
)
from embedagent_core.permissions import OFFICIAL_PERMISSION_CATEGORIES
from embedagent.projection_db import ProjectionDb
from embedagent_core.session import Observation
from embedagent.strategies.tool_cache import ToolResultCache
from embedagent_core.session import Action
from embedagent_core.tool_contracts import (
    ToolCatalogEntry,
    ToolContextPolicy,
    ToolDefinition,
    ToolError,
    ToolExecutionSpec,
    ToolPresentation,
    ToolRuntimePort,
)
from embedagent.tool_result_store import ToolResultStore
from embedagent.tools import (
    authoring_ops,
    discovery_ops,
    file_ops,
    git_ops,
    session_ops,
    shell_ops,
)
from embedagent.tools._base import ToolContext

_VALID_TOOL_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_REGISTERABLE_PERMISSION_CATEGORIES = OFFICIAL_PERMISSION_CATEGORIES
_EXTENSION_REQUIRED_PERMISSION_METADATA = ("permission_category",)
_READ_MODEL_INVALIDATIONS = frozenset(("workspace_files", "tasks", "artifacts", "capabilities"))


def _normalize_read_model_invalidations(tool_name: str, value: Any) -> List[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError("tool %s read_model_invalidations must be a list of strings" % tool_name)
    result = []
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        if text not in _READ_MODEL_INVALIDATIONS:
            raise ValueError(
                "tool %s has unsupported read_model_invalidations value: %s" % (tool_name, text)
            )
        if text not in result:
            result.append(text)
    return result


_DEFAULT_TOOL_METADATA = {
    "read_file": {
        "permission_category": "read",
        "mode_visibility": ["explore", "spec", "build", "debug", "verify"],
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
    "write_file": {
        "permission_category": "workspace_write",
        "mode_visibility": ["spec", "build", "debug"],
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
        "read_model_invalidations": ["workspace_files", "tasks", "artifacts"],
    },
    "edit_file": {
        "permission_category": "workspace_write",
        "mode_visibility": ["build", "debug"],
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
        "read_model_invalidations": ["workspace_files", "tasks", "artifacts"],
    },
    "bash": {
        "permission_category": "shell_exec",
        "mode_visibility": ["build", "debug", "verify"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "Bash",
        "progress_renderer_key": "command",
        "result_renderer_key": "command",
        "supports_diff_preview": False,
        "context_reducer_key": "bash",
        "read_only": False,
        "concurrency_safe": False,
        "interrupt_behavior": "cancel",
        "result_budget_policy": "artifact-first",
        "activity_kind": "command",
        "context_priority": 88,
    },
    "git_status": {
        "permission_category": "read",
        "mode_visibility": ["explore", "build", "debug"],
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
        "mode_visibility": ["explore", "build", "debug"],
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
        "mode_visibility": ["explore", "build", "debug"],
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
    "list_dir": {
        "permission_category": "read",
        "mode_visibility": ["build", "debug", "explore", "spec", "verify"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "List Dir",
        "progress_renderer_key": "list",
        "result_renderer_key": "list",
        "supports_diff_preview": False,
        "context_reducer_key": "list_dir",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "list",
        "context_priority": 72,
    },
    "glob_files": {
        "permission_category": "read",
        "mode_visibility": ["build", "debug", "explore", "spec", "verify"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "Glob Files",
        "progress_renderer_key": "search",
        "result_renderer_key": "search",
        "supports_diff_preview": False,
        "context_reducer_key": "glob_files",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "search",
        "context_priority": 78,
    },
    "grep_text": {
        "permission_category": "read",
        "mode_visibility": ["build", "debug", "explore", "spec", "verify"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "Grep Text",
        "progress_renderer_key": "search",
        "result_renderer_key": "search",
        "supports_diff_preview": False,
        "context_reducer_key": "grep_text",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "search",
        "context_priority": 86,
    },
    "ask_user": {
        "permission_category": "read",
        "mode_visibility": ["explore", "spec", "build", "debug", "verify"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "Ask User",
        "progress_renderer_key": "interaction",
        "result_renderer_key": "interaction",
        "supports_diff_preview": False,
        "context_reducer_key": "ask_user",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "interaction",
        "context_priority": 99,
    },
    "author_local_capability": {
        "permission_category": "workspace_write",
        "mode_visibility": ["build", "debug"],
        "workflow_visibility": ["chat", "plan", "command"],
        "user_label": "Author Local Capability",
        "progress_renderer_key": "file_write",
        "result_renderer_key": "file_write",
        "supports_diff_preview": True,
        "context_reducer_key": "author_local_capability",
        "read_only": False,
        "concurrency_safe": False,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "edit",
        "context_priority": 82,
        "read_model_invalidations": ["workspace_files", "tasks", "artifacts"],
    },
}


class ToolRuntime(ToolRuntimePort):
    def __init__(
        self, workspace: str, app_config=None, cache: Optional[ToolResultCache] = None
    ) -> None:
        self.workspace = os.path.realpath(workspace)
        self.tool_result_store = ToolResultStore(self.workspace)
        self.projection_db = ProjectionDb(
            os.path.join(self.workspace, ".embedagent", "memory", "projections.sqlite3")
        )
        self._ctx = ToolContext(self.workspace, app_config=app_config)
        self.app_config = app_config  # Optional AppConfig; used by loop for path write checking
        self._cache = (
            cache
            if cache is not None
            else ToolResultCache(tool_result_store=self.tool_result_store)
        )
        core_tools = (
            file_ops.build_tools(self._ctx)
            + discovery_ops.build_tools(self._ctx)
            + session_ops.build_interaction_tools(self._ctx)
            + authoring_ops.build_tools(self._ctx)
            + shell_ops.build_tools(self._ctx)
            + git_ops.build_tools(self._ctx)
        )
        self._catalog = {}  # type: Dict[str, ToolCatalogEntry]
        self._tools = {}  # type: Dict[str, ToolDefinition]
        for tool in core_tools:
            self.register_tool(
                tool,
                source_id="embedagent.core",
                source_type="builtin",
            )

    def path_resolver(self):
        return self._ctx

    def register_tool(
        self,
        tool: ToolDefinition,
        source_id: str = "",
        source_type: str = "extension",
        replace: bool = False,
    ) -> None:
        source_type = str(source_type or "extension").strip()
        source_id = str(source_id or source_type or "runtime").strip()
        if replace:
            raise ValueError("tool replacement is not enabled in this slice")
        self._validate_tool_definition(tool, source_type)
        existing = self._catalog.get(tool.name)
        if existing is not None:
            if not (existing.source_type == source_type and existing.source_id == source_id):
                raise ValueError("tool already registered: %s" % tool.name)
        metadata = self._metadata_for_tool(tool, source_type)
        tool.metadata = metadata
        tool.read_only = bool(metadata.get("read_only"))
        tool.concurrency_safe = bool(metadata.get("concurrency_safe"))
        tool.interrupt_behavior = str(metadata.get("interrupt_behavior") or "block")
        tool.result_budget_policy = str(metadata.get("result_budget_policy") or "default")
        tool.activity_kind = str(metadata.get("activity_kind") or "tool")
        tool.context_priority = int(metadata.get("context_priority") or 50)
        self._tools[tool.name] = tool
        self._catalog[tool.name] = self._catalog_entry_for_tool(
            tool,
            metadata,
            source_type=source_type,
            source_id=source_id,
        )

    def _validate_tool_definition(self, tool: ToolDefinition, source_type: str) -> None:
        if not isinstance(tool, ToolDefinition):
            raise ValueError("registered tool must be a ToolDefinition")
        name = str(getattr(tool, "name", "") or "").strip()
        if not name or not _VALID_TOOL_NAME_RE.match(name):
            raise ValueError("invalid tool name: %s" % (name or "<empty>"))
        if not callable(getattr(tool, "handler", None)):
            raise ValueError("tool %s is missing a callable handler" % name)
        if not isinstance(getattr(tool, "parameters", None), dict):
            raise ValueError("tool %s parameters must be an object schema" % name)
        if source_type == "extension":
            raw_metadata = dict(getattr(tool, "metadata", {}) or {})
            missing = []
            for key in _EXTENSION_REQUIRED_PERMISSION_METADATA:
                if key not in raw_metadata:
                    missing.append(key)
            if missing:
                raise ValueError(
                    "tool %s missing metadata: %s" % (name, ", ".join(sorted(missing)))
                )

    def _metadata_for_tool(self, tool: ToolDefinition, source_type: str) -> Dict[str, Any]:
        del source_type
        raw_metadata = dict(getattr(tool, "metadata", {}) or {})
        metadata = self._build_default_metadata(tool.name)
        if tool.name not in _DEFAULT_TOOL_METADATA:
            metadata.update(
                {
                    "read_only": bool(getattr(tool, "read_only", False)),
                    "concurrency_safe": bool(getattr(tool, "concurrency_safe", False)),
                    "interrupt_behavior": str(getattr(tool, "interrupt_behavior", "") or "block"),
                    "result_budget_policy": str(
                        getattr(tool, "result_budget_policy", "") or "default"
                    ),
                    "activity_kind": str(getattr(tool, "activity_kind", "") or "tool"),
                    "context_priority": int(getattr(tool, "context_priority", 50) or 50),
                }
            )
        metadata.update(raw_metadata)
        category = str(metadata.get("permission_category") or "").strip()
        if category not in _REGISTERABLE_PERMISSION_CATEGORIES:
            raise ValueError(
                "tool %s has unsupported permission category: %s"
                % (tool.name, category or "<empty>")
            )
        metadata["read_model_invalidations"] = _normalize_read_model_invalidations(
            tool.name,
            metadata.get("read_model_invalidations"),
        )
        return metadata

    def _catalog_entry_for_tool(
        self,
        tool: ToolDefinition,
        metadata: Dict[str, Any],
        source_type: str,
        source_id: str,
    ) -> ToolCatalogEntry:
        return ToolCatalogEntry(
            name=tool.name,
            description=tool.description,
            permission_category=str(metadata.get("permission_category") or "read"),
            mode_visibility=list(metadata.get("mode_visibility") or []),
            workflow_visibility=list(metadata.get("workflow_visibility") or []),
            execution=ToolExecutionSpec(
                read_only=bool(metadata.get("read_only")),
                concurrency_safe=bool(metadata.get("concurrency_safe")),
                interrupt_behavior=str(metadata.get("interrupt_behavior") or "block"),
                result_budget_policy=str(metadata.get("result_budget_policy") or "default"),
            ),
            presentation=ToolPresentation(
                user_label=str(metadata.get("user_label") or tool.name),
                progress_renderer_key=str(metadata.get("progress_renderer_key") or "default"),
                result_renderer_key=str(metadata.get("result_renderer_key") or "default"),
                supports_diff_preview=bool(metadata.get("supports_diff_preview")),
            ),
            context_policy=ToolContextPolicy(
                context_reducer_key=str(metadata.get("context_reducer_key") or tool.name),
                activity_kind=str(metadata.get("activity_kind") or "tool"),
                context_priority=int(metadata.get("context_priority") or 50),
                read_model_invalidations=list(metadata.get("read_model_invalidations") or []),
            ),
            source_type=source_type,
            source_id=source_id,
        )

    def schemas(self) -> List[Dict[str, Any]]:
        return [td.schema() for td in self._tools.values()]

    def schemas_for(
        self,
        mode_name: str,
        workflow_state: str = "chat",
        tool_names: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        if tool_names is None:
            return []
        schemas = []
        seen = set()
        for name in list(tool_names or []):
            if name in seen:
                continue
            seen.add(name)
            tool = self._tools.get(name)
            if tool is None:
                continue
            entry = self._catalog.get(name)
            if entry is not None and entry.workflow_visibility:
                if (
                    workflow_state not in entry.workflow_visibility
                    and "any" not in entry.workflow_visibility
                ):
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

    def reload_resources(
        self,
        skill_paths: Optional[List[str]] = None,
        prompt_paths: Optional[List[str]] = None,
        recipe_paths: Optional[List[str]] = None,
        reason: str = "reload",
    ) -> Dict[str, Any]:
        return self._ctx.reload_resources(
            skill_paths=skill_paths,
            prompt_paths=prompt_paths,
            recipe_paths=recipe_paths,
            reason=reason,
        )

    def local_resources(self) -> Dict[str, Any]:
        return self._ctx.local_resources()

    def capability_descriptors(self) -> List[Any]:
        descriptors = runtime_tool_capability_descriptors(self)
        descriptors.extend(resource_capability_descriptors(self.local_resources()))
        return descriptors

    def workspace_recipes(self) -> Dict[str, Any]:
        return self._ctx.list_workspace_recipes()

    def execute(self, name: str, arguments: Dict[str, Any]) -> Observation:
        return self.execute_with_interrupt(name, arguments, None)

    def execute_with_cache(
        self,
        action_name: str,
        arguments: Dict[str, Any],
        session_id: str = "",
        use_cache: bool = True,
    ) -> Observation:
        if not use_cache:
            return self.execute_with_interrupt(action_name, arguments, None)

        action = Action(name=action_name, arguments=arguments, call_id="", raw_arguments=arguments)

        # Check cache
        cached = self._cache.get(action, session_id)
        if cached is not None:
            return cached

        # Execute and cache if successful
        observation = self.execute_with_interrupt(action_name, arguments, None)
        if observation.success:
            self._cache.put(action, observation, session_id)

        return observation

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
            data = (
                exc.to_observation_data()
                if hasattr(exc, "to_observation_data")
                else {"error_kind": "tool_error", "retryable": True}
            )
            return self._enrich_observation(
                name,
                Observation(tool_name=name, success=False, error=str(exc), data=data),
            )
        except (RuntimeError, ValueError, TypeError) as exc:
            return self._enrich_observation(
                name,
                Observation(
                    tool_name=name,
                    success=False,
                    error="工具执行失败：%s" % exc,
                    data={"error_kind": "tool_error", "retryable": True},
                ),
            )
        finally:
            self._ctx.clear_interrupt_event()
        return self._enrich_observation(name, observation)

    def _enrich_observation(self, name: str, observation: Observation) -> Observation:
        observation.tool_name = name
        if isinstance(observation.data, dict):
            entry = self._catalog.get(name)
            if entry is not None:
                data = dict(observation.data)
                data.setdefault("tool_label", entry.presentation.user_label)
                data.setdefault("permission_category", entry.permission_category)
                data.setdefault(
                    "supports_diff_preview",
                    entry.presentation.supports_diff_preview,
                )
                data.setdefault("progress_renderer_key", entry.presentation.progress_renderer_key)
                data.setdefault("result_renderer_key", entry.presentation.result_renderer_key)
                data.setdefault(
                    "read_model_invalidations",
                    list(entry.context_policy.read_model_invalidations),
                )
                data.setdefault("source_type", entry.source_type)
                data.setdefault("source_id", entry.source_id)
                observation.data = data
        return observation

    def _build_default_metadata(self, name: str) -> Dict[str, Any]:
        default = _DEFAULT_TOOL_METADATA.get(name, {})
        if default:
            return dict(default)
        return {
            "permission_category": "read",
            "mode_visibility": ["explore", "spec", "build", "debug", "verify"],
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
            "read_model_invalidations": [],
        }
