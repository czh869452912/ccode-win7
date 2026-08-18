from __future__ import annotations

import re
from typing import Any, List, Optional, Set

from embedagent_core.extensions import (
    ExtensionCapability,
    ToolRegistrationResult,
    WorkflowPatch,
    WorkflowPrompt,
)
from embedagent_core.session import Observation

from embedagent_workflow_cpp import task_store
from embedagent_workflow_cpp.context_reducers import register_c_workflow_context_reducers
from embedagent_workflow_cpp.package_manifest import c_workflow_package_manifest_dict
from embedagent_workflow_cpp.packs import pack_tool_names
from embedagent_workflow_cpp.runner import HarnessRunner
from embedagent_workflow_cpp.session_graph_state import HarnessSessionGraphState
from embedagent_workflow_cpp.task_graph import TaskGraph
from embedagent_workflow_cpp.tool_registry import build_c_workflow_tools
from embedagent_workflow_cpp.workflow_projection import (
    build_c_harness_workflow_projection,
)
from embedagent_workflow_cpp.workspace_recipes import (
    list_workspace_recipes,
    resolve_workspace_recipe,
)


class CHarnessWorkflowExtension(object):
    def __init__(
        self,
        tools: Any = None,
        harness_runner: Optional[HarnessRunner] = None,
        graph_state: Optional[HarnessSessionGraphState] = None,
    ) -> None:
        self.tools = tools
        self.harness_runner = harness_runner or HarnessRunner()
        self.graph_state = graph_state or HarnessSessionGraphState()

    def dispose(self) -> None:
        self.graph_state.dispose()

    def extension_capabilities(self) -> List[ExtensionCapability]:
        return [
            ExtensionCapability("should_inject_workflow", self.should_inject_workflow),
            ExtensionCapability("describe_prompt", self.describe_prompt),
            ExtensionCapability("initialize_workflow_state", self.initialize_workflow_state),
            ExtensionCapability("package_manifest", self.package_manifest),
            ExtensionCapability("allowed_tool_names", self.allowed_tool_names),
            ExtensionCapability("register_tools", self.register_tools),
            ExtensionCapability("register_context_reducers", self.register_context_reducers),
            ExtensionCapability("workspace_recipes", self.list_workspace_recipes),
            ExtensionCapability("load_session_tasks", self.load_session_tasks),
            ExtensionCapability("handle_tool_call", self.handle_tool_call),
        ]

    def should_inject_workflow(self, user_text: str, current_mode: str) -> bool:
        if current_mode in ("explore", "verify"):
            return False
        text = str(user_text or "").strip()
        text_lower = text.lower()
        chat_patterns = [
            r"^\s*hi\b",
            r"^\s*hello\b",
            r"^\s*hey\b",
            r"what can you do",
            r"who are you",
            r"help\s*$",
            r"^\s*thanks?\b",
            r"^\s*ok\b",
            r"^\s*bye\b",
            r"^\s*你好[！!。？?]*\s*$",
            r"^\s*嗨[！!。？?]*\s*$",
            r"^\s*你能做什么[？?]?\s*$",
            r"^\s*你是谁[？?]?\s*$",
            r"^\s*帮助[！!。？?]*\s*$",
            r"^\s*谢谢[！!。？?]*\s*$",
            r"^\s*好的[！!。？?]*\s*$",
            r"^\s*再见[！!。？?]*\s*$",
        ]
        is_chat = any(re.search(pattern, text_lower) for pattern in chat_patterns)
        if is_chat:
            return False
        english_work_indicators = [
            "build",
            "compile",
            "fix",
            "debug",
            "implement",
            "create",
            "write",
            "generate",
            "refactor",
            "optimize",
            "test",
            "verify",
            "check",
            "run",
            "execute",
        ]
        chinese_work_indicators = [
            "构建",
            "编译",
            "修复",
            "调试",
            "实现",
            "创建",
            "新增",
            "写",
            "生成",
            "重构",
            "优化",
            "测试",
            "验证",
            "检查",
            "运行",
            "执行",
            "定位",
            "崩溃",
            "报错",
            "失败",
            "函数",
            "项目",
        ]
        return any(ind in text_lower for ind in english_work_indicators) or any(
            ind in text for ind in chinese_work_indicators
        )

    def describe_prompt(
        self,
        current_mode: str,
        workflow_state: str = "",
        session: Any = None,
    ) -> Optional[WorkflowPrompt]:
        context = self._describe_context(current_mode, workflow_state=workflow_state)
        if context is None:
            return None
        del session
        return WorkflowPrompt(
            mode_name=str(context.mode_name or ""),
            discipline_label=str(context.discipline_label or ""),
            pack_name=str(context.pack_name or ""),
            prompt_units=list(context.prompt_units or []),
        )

    def initialize_workflow_state(
        self,
        session: Any,
        user_text: str,
        current_mode: str,
        workflow_state: str = "",
    ) -> Optional[WorkflowPatch]:
        graph = self.graph_state.get(session)
        session_workflow = dict(getattr(session, "workflow_state", {}) or {}).get("workflow")
        has_existing_workflow = isinstance(session_workflow, dict) and bool(session_workflow)
        should_initialize = self.should_inject_workflow(user_text, current_mode)
        if graph is None:
            if not should_initialize and not has_existing_workflow:
                return None
            graph = TaskGraph.empty()
        if graph.is_empty() and should_initialize:
            graph = TaskGraph.from_user_request(user_text, current_mode)
        if graph.is_empty() and not has_existing_workflow:
            return None
        graph = graph.clone()
        discipline_override = self._discipline_override(current_mode, workflow_state)
        graph = self.harness_runner.update_task_graph(
            graph,
            current_mode,
            observations=[],
            discipline_override=discipline_override,
        )
        context = None
        if not graph.is_empty():
            context = self._describe_context(
                current_mode,
                workflow_state=workflow_state,
                current_phase=str(getattr(graph, "current_phase", "") or ""),
                observations=[],
            )
        return self._workflow_patch(
            graph,
            context=context,
            reason="initialize_workflow_state",
        )

    def sync_session_workflow(
        self,
        session: Any,
        current_mode: str,
        workflow_state: str = "",
        observations: Optional[List[Any]] = None,
    ) -> Optional[WorkflowPatch]:
        graph = self.graph_state.get(session)
        if graph is None:
            return None
        context = None
        if not graph.is_empty():
            context = self._describe_context(
                current_mode,
                workflow_state=workflow_state,
                current_phase=str(getattr(graph, "current_phase", "") or ""),
                observations=observations or [],
            )
        return self._workflow_patch(
            graph,
            context=context,
            reason="sync_session_workflow",
        )

    def refresh_managed_session(
        self,
        managed_session: Any,
        workspace: str,
        observations: Optional[List[Any]] = None,
        task_store_module: Any = None,
    ) -> None:
        del observations
        store = task_store_module or task_store
        projection = dict(getattr(managed_session, "projection", {}) or {})
        workflow_state = dict(projection.get("workflow_state") or {})
        workflow = dict(workflow_state.get("workflow") or {})
        metadata = workflow.get("metadata") or {}
        store.save_task_snapshot(
            workspace,
            managed_session.session_id,
            managed_session.current_mode,
            managed_session.workflow_state,
            str(metadata.get("discipline_profile") or ""),
            str(metadata.get("current_phase") or ""),
            str(workflow.get("summary") or ""),
            list(workflow.get("items") or []),
            snapshot_schema_version=2,
            source_event_count=int(projection.get("restore_transcript_event_count") or 0),
            workflow_fingerprint=store.workflow_fingerprint(workflow),
        )

    def build_mode_context(
        self,
        session: Any,
        current_mode: str,
        workflow_state: str = "",
    ) -> Any:
        graph = self.graph_state.get(session)
        return self._describe_context(
            current_mode,
            workflow_state=workflow_state,
            current_phase=(
                str(getattr(graph, "current_phase", "") or "") if graph is not None else ""
            ),
        )

    def package_manifest(self) -> dict:
        return c_workflow_package_manifest_dict()

    def allowed_tool_names(self, mode_name: str, workflow_state: str = "") -> Set[str]:
        context = self._describe_context(mode_name, workflow_state=workflow_state)
        if context is None:
            return set()
        return set(pack_tool_names(context.pack_name))

    def register_tools(self, event: Any, context: Any) -> ToolRegistrationResult:
        del event
        registry = getattr(context, "tool_registry", None)
        tool_context = getattr(registry, "_ctx", None)
        if tool_context is None:
            return ToolRegistrationResult(
                tools=[],
                source_id="embedagent_workflow_cpp",
                source_type="workflow_package",
            )
        register_recipe_provider = getattr(registry, "set_workspace_recipe_provider", None)
        if callable(register_recipe_provider):
            register_recipe_provider(self.list_workspace_recipes)
        return ToolRegistrationResult(
            tools=build_c_workflow_tools(_CWorkflowToolContext(tool_context, self)),
            source_id="embedagent_workflow_cpp",
            source_type="workflow_package",
        )

    def list_workspace_recipes(self) -> dict:
        workspace = self._workspace()
        if not workspace:
            return {"workspace": "", "items": []}
        resource_payload = self._resource_snapshot()
        return list_workspace_recipes(
            workspace,
            local_recipe_records=resource_payload.get("recipes") or [],
            resource_metadata=resource_payload,
        )

    def resolve_workspace_recipe(
        self,
        recipe_id: str,
        expected_tool_name: str = "",
        target: str = "",
        profile: str = "",
    ) -> dict:
        resource_payload = self._resource_snapshot()
        return resolve_workspace_recipe(
            self._workspace(),
            recipe_id=recipe_id,
            expected_tool_name=expected_tool_name,
            target=target,
            profile=profile,
            local_recipe_records=resource_payload.get("recipes") or [],
            resource_metadata=resource_payload,
        )

    def _workspace(self) -> str:
        return str(getattr(self.tools, "workspace", "") or "")

    def _resource_snapshot(self) -> dict:
        local_resources = getattr(self.tools, "local_resources", None)
        if not callable(local_resources):
            return {}
        payload = local_resources()
        if not isinstance(payload, dict):
            return {}
        return dict(payload)

    def register_context_reducers(self, reducer_registry: Any):
        return register_c_workflow_context_reducers(reducer_registry)

    def load_session_tasks(self, workspace: str, session_id: str) -> dict:
        tasks = task_store.load_task_items(workspace, session_id)
        return {
            "count": len(tasks),
            "tasks": tasks,
            "path": task_store.relative_task_snapshot_path(session_id),
            "session_id": str(session_id or ""),
        }

    def handle_tool_call(
        self,
        session: Any,
        tool_name: str,
        current_mode: str,
        workflow_state: str = "",
    ) -> Optional[Observation]:
        if tool_name != "task_status":
            return None
        summary = ""
        phase = ""
        discipline = ""
        task_items = []  # type: List[Any]
        graph = self.graph_state.get(session)
        if graph is not None and not graph.is_empty():
            mode_context = self._describe_context(current_mode, workflow_state=workflow_state)
            if mode_context is not None:
                summary = str(getattr(mode_context, "task_summary", "") or "")
                phase = str(getattr(mode_context, "current_phase", "") or "")
                discipline = str(getattr(mode_context, "discipline_label", "") or "")
                task_items = list(getattr(mode_context, "task_items", []) or [])
        if not summary:
            summary = "no active tasks"
        lines = [line for line in summary.splitlines() if line]
        return Observation(
            tool_name="task_status",
            success=True,
            error=None,
            data={
                "summary": summary,
                "preview": lines,
                "returned_count": len(lines),
                "total_count": len(lines),
                "has_more": False,
                "next_offset": 0,
                "result_ref": "",
                "current_mode": current_mode,
                "current_phase": phase,
                "discipline_profile": discipline,
                "tasks": task_items,
            },
        )

    def _describe_context(
        self,
        mode_name: str,
        workflow_state: str = "",
        current_phase: str = "",
        observations: Optional[List[Any]] = None,
    ) -> Any:
        if self.tools is not None:
            describe = getattr(self.tools, "describe_mode", None)
            if callable(describe):
                return describe(
                    mode_name,
                    workflow_state=workflow_state,
                    current_phase=current_phase,
                    observations=observations or [],
                )
        discipline_override = self._discipline_override(mode_name, workflow_state)
        return self.harness_runner.describe_mode(
            mode_name,
            discipline_override=discipline_override,
            current_phase=current_phase,
            observations=observations or [],
        )

    def _discipline_override(self, mode_name: str, workflow_state: str = "") -> Optional[str]:
        if str(mode_name or "") == "build" and str(workflow_state or "") == "plan":
            return "full_spec_tdd"
        return None

    def _workflow_patch(
        self,
        graph: Any,
        context: Any = None,
        reason: str = "",
    ) -> Optional[WorkflowPatch]:
        if graph is None:
            return None
        return WorkflowPatch(
            workflow=build_c_harness_workflow_projection(graph, context=context),
            metadata={
                "source": "embedagent_workflow_cpp",
                "reason": str(reason or ""),
            },
        )


class _CWorkflowToolContext(object):
    def __init__(self, base_context: Any, extension: CHarnessWorkflowExtension) -> None:
        self._base_context = base_context
        self._extension = extension

    def list_workspace_recipes(self) -> dict:
        return self._extension.list_workspace_recipes()

    def resolve_workspace_recipe(
        self,
        recipe_id: str,
        expected_tool_name: str = "",
        target: str = "",
        profile: str = "",
    ) -> dict:
        return self._extension.resolve_workspace_recipe(
            recipe_id,
            expected_tool_name=expected_tool_name,
            target=target,
            profile=profile,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base_context, name)
