"""
Agent Core 适配器 - 实现 CoreInterface
将当前 InProcessAdapter / QueryEngine 主链路包装为协议接口
"""

from __future__ import annotations

import difflib
import threading
import uuid
from typing import Any, Dict, List, Optional

from embedagent.di_container import get_default_container
from embedagent.modes import DEFAULT_MODE
from embedagent.protocol import (
    CommandResult,
    CoreInterface,
    DiffPreview,
    FrontendCallbacks,
    Message,
    MessageType,
    PermissionContextView,
    PermissionRequest,
    PlanSnapshot,
    RuntimeEnvironmentSnapshot,
    SessionSnapshot,
    SessionStatus,
    ToolCall,
    ToolResult,
    UserInputRequest,
    WorkspaceInfo,
)

_SESSION_EVENT_NAMES: frozenset = frozenset(
    {
        "turn_start",
        "turn_end",
        "step_start",
        "step_end",
        "tool_started",
        "tool_finished",
        "permission_required",
        "user_input_required",
        "session_finished",
        "session_error",
    }
)
_TASK_INVALIDATION = "tasks"
_ARTIFACT_INVALIDATION = "artifacts"


def _read_model_invalidations(payload: Dict[str, Any]) -> List[str]:
    values = []
    raw = payload.get("read_model_invalidations")
    if not raw and isinstance(payload.get("data"), dict):
        raw = payload["data"].get("read_model_invalidations")
    for item in list(raw or []):
        text = str(item or "").strip()
        if text and text not in values:
            values.append(text)
    return values


def get_inprocess_adapter(fresh: bool = False):
    """Return the InProcessAdapter class.

    Use fresh=True in tests to get an isolated reference.
    """
    return get_default_container().resolve("inprocess_adapter", fresh=fresh)


def _register_adapter_factory() -> None:
    from embedagent.inprocess_adapter import InProcessAdapter

    get_default_container().register_factory(
        "inprocess_adapter",
        lambda: InProcessAdapter,
    )


_register_adapter_factory()


def _status_from_snapshot(snapshot: Dict[str, Any]) -> SessionStatus:
    status_map = {
        "idle": SessionStatus.IDLE,
        "running": SessionStatus.RUNNING,
        "waiting_permission": SessionStatus.WAITING_PERMISSION,
        "waiting_user_input": SessionStatus.WAITING_INPUT,
        "error": SessionStatus.ERROR,
    }
    return status_map.get(snapshot.get("status"), SessionStatus.IDLE)


def _runtime_environment_from_snapshot(snapshot: Dict[str, Any]) -> RuntimeEnvironmentSnapshot:
    runtime = snapshot.get("runtime_environment") or {}
    return RuntimeEnvironmentSnapshot(
        runtime_source=str(runtime.get("runtime_source") or snapshot.get("runtime_source") or ""),
        bundled_tools_ready=bool(
            runtime.get("bundled_tools_ready", snapshot.get("bundled_tools_ready", False))
        ),
        fallback_warnings=list(
            runtime.get("fallback_warnings") or snapshot.get("fallback_warnings") or []
        ),
        resolved_tool_roots=dict(runtime.get("resolved_tool_roots") or {}),
        tool_sources=dict(runtime.get("tool_sources") or {}),
    )


def _session_snapshot_from_dict(snapshot: Dict[str, Any]) -> SessionSnapshot:
    return SessionSnapshot(
        session_id=snapshot.get("session_id", ""),
        status=_status_from_snapshot(snapshot),
        current_mode=snapshot.get("current_mode") or DEFAULT_MODE,
        created_at=snapshot.get("started_at", ""),
        updated_at=snapshot.get("updated_at", ""),
        workflow_state=snapshot.get("workflow_state", "chat"),
        has_active_plan=bool(snapshot.get("has_active_plan", False)),
        active_plan_ref=snapshot.get("active_plan_ref", ""),
        current_command_context=snapshot.get("current_command_context", ""),
        last_error=snapshot.get("last_error"),
        runtime_source=str(snapshot.get("runtime_source") or ""),
        bundled_tools_ready=bool(snapshot.get("bundled_tools_ready", False)),
        fallback_warnings=list(snapshot.get("fallback_warnings") or []),
        runtime_environment=_runtime_environment_from_snapshot(snapshot),
        compact_summary_text=str(snapshot.get("compact_summary_text") or ""),
        context_analysis=dict(snapshot.get("context_analysis") or {}),
        context_usage=dict(snapshot.get("context_usage") or {}),
        compact_boundary_count=int(snapshot.get("compact_boundary_count") or 0),
        workspace_intelligence=list(snapshot.get("workspace_intelligence") or []),
        context_pipeline_steps=list(snapshot.get("context_pipeline_steps") or []),
        last_transition_reason=str(snapshot.get("last_transition_reason") or ""),
        last_transition_message=str(snapshot.get("last_transition_message") or ""),
        last_transition_display_reason=str(snapshot.get("last_transition_display_reason") or ""),
        recent_transition_reasons=list(snapshot.get("recent_transition_reasons") or []),
        recent_transitions=list(snapshot.get("recent_transitions") or []),
        compact_retry_count=int(snapshot.get("compact_retry_count") or 0),
        restore_stop_reason=str(snapshot.get("restore_stop_reason") or ""),
        restore_consumed_event_count=int(snapshot.get("restore_consumed_event_count") or 0),
        restore_transcript_event_count=int(snapshot.get("restore_transcript_event_count") or 0),
        compaction_state=dict(snapshot.get("compaction_state") or {}),
        recovery_state=dict(snapshot.get("recovery_state") or {}),
        turn_experience=dict(snapshot.get("turn_experience") or {}),
        pending_interaction=(
            dict(snapshot.get("pending_interaction") or {})
            if isinstance(snapshot.get("pending_interaction"), dict)
            else None
        ),
        pending_interaction_valid=bool(
            snapshot.get(
                "pending_interaction_valid",
                bool(snapshot.get("pending_interaction")),
            )
        ),
        current_phase=str(snapshot.get("current_phase") or ""),
        discipline_profile=str(snapshot.get("discipline_profile") or ""),
        current_activity=str(snapshot.get("current_activity") or ""),
        task_summary=str(snapshot.get("task_summary") or ""),
        task_items=list(snapshot.get("task_items") or []),
    )


class CallbackBridge:
    """回调桥接器 - 将 callback 转换为 Protocol 类型"""

    def __init__(self, frontend: FrontendCallbacks):
        self.frontend = frontend

    def emit(self, event_name: str, session_id: str, payload: Dict[str, Any]) -> None:
        """处理来自 Adapter 的事件"""
        if event_name == "assistant_delta":
            self.frontend.on_stream_delta(
                payload.get("text", ""),
                {
                    "turn_id": payload.get("turn_id", ""),
                    "step_id": payload.get("step_id", ""),
                    "step_index": payload.get("step_index", 0),
                },
            )

        elif event_name == "tool_started":
            arguments = payload.get("arguments", {})
            if not isinstance(arguments, dict):
                arguments = {}
            arguments = dict(arguments)
            if payload.get("tool_label"):
                arguments["_tool_label"] = payload.get("tool_label")
            if payload.get("permission_category"):
                arguments["_permission_category"] = payload.get("permission_category")
            if "supports_diff_preview" in payload:
                arguments["_supports_diff_preview"] = bool(payload.get("supports_diff_preview"))
            if payload.get("progress_renderer_key"):
                arguments["_progress_renderer_key"] = payload.get("progress_renderer_key")
            if payload.get("result_renderer_key"):
                arguments["_result_renderer_key"] = payload.get("result_renderer_key")
            if isinstance(payload.get("read_model_invalidations"), list):
                arguments["_read_model_invalidations"] = list(
                    payload.get("read_model_invalidations") or []
                )
            call = ToolCall(
                tool_name=payload.get("tool_name", ""),
                arguments=arguments,
                call_id=str(payload.get("call_id") or str(uuid.uuid4())[:8]),
                turn_id=str(payload.get("turn_id") or ""),
                step_id=str(payload.get("step_id") or ""),
                step_index=int(payload.get("step_index") or 0),
                runtime_source=str(payload.get("runtime_source") or ""),
                resolved_tool_roots=(
                    payload.get("resolved_tool_roots", {})
                    if isinstance(payload.get("resolved_tool_roots"), dict)
                    else {}
                ),
            )
            self.frontend.on_tool_start(call)

        elif event_name == "tool_finished":
            read_model_invalidations = _read_model_invalidations(payload)
            result = ToolResult(
                tool_name=payload.get("tool_name", ""),
                success=payload.get("success", False),
                data=payload.get("data", {}),
                error=payload.get("error"),
                call_id=str(payload.get("call_id") or ""),
                turn_id=str(payload.get("turn_id") or ""),
                step_id=str(payload.get("step_id") or ""),
                step_index=int(payload.get("step_index") or 0),
                runtime_source=str(payload.get("runtime_source") or ""),
                resolved_tool_roots=(
                    payload.get("resolved_tool_roots", {})
                    if isinstance(payload.get("resolved_tool_roots"), dict)
                    else {}
                ),
            )
            self.frontend.on_tool_finish(result)
            if _TASK_INVALIDATION in read_model_invalidations and hasattr(
                self.frontend, "on_tasks_refresh"
            ):
                self.frontend.on_tasks_refresh()
            if _ARTIFACT_INVALIDATION in read_model_invalidations and hasattr(
                self.frontend, "on_artifacts_refresh"
            ):
                self.frontend.on_artifacts_refresh()

        elif event_name == "session_error":
            snapshot = payload.get("session_snapshot", {})
            if isinstance(snapshot, dict) and snapshot.get("session_id"):
                self._notify_status_change(snapshot)
            msg = Message(
                id=str(uuid.uuid4()),
                type=MessageType.ERROR,
                content=payload.get("error", "Unknown error"),
                metadata={
                    "turn_id": str(payload.get("turn_id") or ""),
                    "step_id": str(payload.get("step_id") or ""),
                    "step_index": int(payload.get("step_index") or 0),
                    "phase": str(payload.get("phase") or ""),
                },
            )
            self.frontend.on_message(msg)

        elif event_name == "session_status":
            snapshot = payload.get("session_snapshot", {})
            if isinstance(snapshot, dict):
                self._notify_status_change(snapshot)

        elif event_name == "reasoning_delta":
            self.frontend.on_reasoning_delta(
                payload.get("text", ""),
                {
                    "turn_id": payload.get("turn_id", ""),
                    "step_id": payload.get("step_id", ""),
                    "step_index": payload.get("step_index", 0),
                },
            )

        elif event_name == "thinking_state":
            self.frontend.on_thinking_state_change(
                bool(payload.get("active", False)),
                str(payload.get("reason") or ""),
            )

        elif event_name == "command_result":
            self.frontend.on_command_result(
                CommandResult(
                    command_name=str(payload.get("command_name") or ""),
                    success=bool(payload.get("success", False)),
                    message=str(payload.get("message") or ""),
                    data=payload.get("data", {}),
                    turn_id=str(payload.get("turn_id") or ""),
                    step_id=str(payload.get("step_id") or ""),
                    step_index=int(payload.get("step_index") or 0),
                )
            )

        elif event_name == "plan_updated":
            plan = payload.get("plan", {})
            if isinstance(plan, dict):
                self.frontend.on_plan_updated(
                    PlanSnapshot(
                        session_id=str(plan.get("session_id") or session_id),
                        title=str(plan.get("title") or "Current Plan"),
                        content=str(plan.get("content") or ""),
                        updated_at=str(plan.get("updated_at") or ""),
                        workflow_state=str(plan.get("workflow_state") or "plan"),
                        path=str(plan.get("path") or ""),
                        summary=str(plan.get("summary") or ""),
                    )
                )

        elif event_name == "session_finished":
            snapshot = payload.get("session_snapshot", {})
            self._notify_status_change(snapshot)

        if event_name in _SESSION_EVENT_NAMES:
            if hasattr(self.frontend, "on_turn_event"):
                event_payload = dict(payload or {})
                event_payload.setdefault("session_id", session_id)
                self.frontend.on_turn_event(event_name, event_payload)

        elif event_name == "mode_changed":
            snapshot = payload.get("session_snapshot", {})
            if isinstance(snapshot, dict) and snapshot.get("session_id"):
                self._notify_status_change(snapshot)

        elif event_name == "context_compacted":
            stats = payload.get("recent_turns", 0)
            msg = Message(
                id=str(uuid.uuid4()),
                type=MessageType.CONTEXT_COMPACTED,
                content=f"Context compacted: {stats} turns kept",
                metadata={
                    "recent_turns": payload.get("recent_turns", 0),
                    "summarized_turns": payload.get("summarized_turns", 0),
                    "approx_tokens_after": payload.get("approx_tokens_after"),
                    "analysis": payload.get("analysis", {}),
                    "turn_id": str(payload.get("turn_id") or ""),
                    "step_id": str(payload.get("step_id") or ""),
                    "step_index": int(payload.get("step_index") or 0),
                },
            )
            self.frontend.on_message(msg)

    def request_permission(self, payload: Dict[str, Any]) -> bool:
        request = PermissionRequest(
            permission_id=str(payload.get("permission_id", "")),
            tool_name=str(payload.get("tool_name", "")),
            category=str(payload.get("category", "")),
            reason=str(payload.get("reason", "")),
            details=payload.get("details", {}),
            session_id=str(payload.get("session_id", "")),
            turn_id=str(payload.get("turn_id", "")),
            step_id=str(payload.get("step_id", "")),
            step_index=int(payload.get("step_index") or 0),
        )
        return bool(self.frontend.on_permission_request(request))

    def request_user_input(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        request = UserInputRequest(
            request_id=str(payload.get("request_id", "")),
            tool_name=str(payload.get("tool_name", "")),
            question=str(payload.get("question", "")),
            options=payload.get("options", []),
            details=payload.get("details", {}),
            session_id=str(payload.get("session_id", "")),
            turn_id=str(payload.get("turn_id", "")),
            step_id=str(payload.get("step_id", "")),
            step_index=int(payload.get("step_index") or 0),
        )
        answer = self.frontend.on_user_input_request(request)
        if answer is None:
            return None
        if isinstance(answer, dict):
            return answer
        return {"answer": str(answer)}

    def _notify_status_change(self, snapshot: Dict[str, Any]) -> None:
        """通知状态变化"""
        self.frontend.on_session_status_change(_session_snapshot_from_dict(snapshot))


class AgentCoreAdapter(CoreInterface):
    """
    Agent Core 适配器
    包装现有的 InProcessAdapter，实现 CoreInterface
    """

    def __init__(self, workspace: str, config: Optional[Dict[str, Any]] = None):
        self.workspace = workspace
        self.config = config or {}
        self._adapter = None
        self._frontend: Optional[FrontendCallbacks] = None
        self._callback_bridge: Optional[CallbackBridge] = None
        self._lock = threading.RLock()

    def initialize(self, client, tools, **kwargs) -> None:
        """初始化内部 Adapter"""
        AdapterClass = get_inprocess_adapter()
        adapter_kwargs = {
            "client": client,
            "tools": tools,
            "max_turns": kwargs.get("max_turns"),
            "permission_policy": kwargs.get("permission_policy"),
            "event_handler": self._on_adapter_event,
        }
        for key in (
            "summary_store",
            "project_memory_store",
            "context_manager",
            "memory_maintenance",
            "maintenance_interval",
        ):
            if key in kwargs and kwargs.get(key) is not None:
                adapter_kwargs[key] = kwargs.get(key)
        self._adapter = AdapterClass(**adapter_kwargs)

    def attach_adapter(self, adapter) -> None:
        """Attach a hosted InProcessAdapter built outside this protocol wrapper."""
        self._adapter = adapter

    def register_frontend(self, frontend: FrontendCallbacks) -> None:
        """注册前端回调"""
        self._frontend = frontend
        self._callback_bridge = CallbackBridge(frontend)

    def _on_adapter_event(self, event_name: str, session_id: str, payload: Dict[str, Any]) -> None:
        """处理 Adapter 事件"""
        if self._callback_bridge:
            self._callback_bridge.emit(event_name, session_id, payload)

    def _snapshot_to_protocol(self, snapshot: Dict[str, Any]) -> SessionSnapshot:
        """转换快照格式"""
        return _session_snapshot_from_dict(snapshot)

    # ============ CoreInterface 实现 ============

    def create_session(self, mode: str) -> SessionSnapshot:
        snapshot = self._adapter.create_session(mode=mode)
        return self._snapshot_to_protocol(snapshot)

    def resume_session(self, reference: str, mode: str) -> SessionSnapshot:
        snapshot = self._adapter.resume_session(reference, mode)
        return self._snapshot_to_protocol(snapshot)

    def list_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self._adapter.list_sessions(limit=limit)

    def get_session_snapshot(self, session_id: str) -> SessionSnapshot:
        return self._snapshot_to_protocol(self._adapter.get_session_snapshot(session_id))

    def get_session_bootstrap(self, session_id: str) -> Dict[str, Any]:
        payload = self._adapter.get_session_bootstrap(session_id)
        snapshot = payload.get("snapshot") if isinstance(payload, dict) else None
        result = dict(payload or {})
        result["snapshot"] = self._snapshot_to_protocol(snapshot or {})
        return result

    def get_session_capabilities(self, session_id: str = "") -> Dict[str, Any]:
        return self._adapter.get_session_capabilities(session_id=session_id)

    def rename_session(self, session_id: str, title: str) -> Dict[str, Any]:
        return self._adapter.rename_session(session_id, title)

    def archive_session(self, session_id: str) -> Dict[str, Any]:
        return self._adapter.archive_session(session_id)

    def fork_session(self, session_id: str, title: str = "") -> Dict[str, Any]:
        return self._adapter.fork_session(session_id, title=title)

    def submit_message(self, session_id: str, text: str) -> None:
        """异步提交消息"""

        def run():
            try:
                self._adapter.submit_user_message(
                    session_id=session_id,
                    text=text,
                    stream=True,
                    wait=True,
                    permission_resolver=None,
                    user_input_resolver=None,
                    event_handler=self._on_adapter_event,
                )
            except (RuntimeError, ValueError, TypeError) as e:
                if self._frontend:
                    self._frontend.on_message(
                        Message(id=str(uuid.uuid4()), type=MessageType.ERROR, content=str(e))
                    )

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def cancel_session(self, session_id: str) -> SessionSnapshot:
        return self._snapshot_to_protocol(self._adapter.cancel_session(session_id))

    def set_mode(self, session_id: str, mode: str) -> None:
        self._adapter.set_session_mode(session_id, mode)

    def respond_to_interaction(
        self, session_id: str, interaction_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        return self._adapter.respond_to_interaction(session_id, interaction_id, payload)

    def get_workspace_snapshot(self) -> WorkspaceInfo:
        snapshot = self._adapter.get_workspace_snapshot()
        git_info = snapshot.get("git", {})
        tree_info = snapshot.get("tree", {})
        return WorkspaceInfo(
            path=snapshot.get("workspace", ""),
            git_branch=git_info.get("branch", ""),
            git_dirty=git_info.get("dirty_count", 0),
            file_count=tree_info.get("file_count", 0),
            dir_count=tree_info.get("dir_count", 0),
        )

    def list_workspace_recipes(self) -> Dict[str, Any]:
        return self._adapter.list_workspace_recipes()

    def reload_resources(self, session_id: str = "", reason: str = "api") -> Dict[str, Any]:
        return self._adapter.reload_resources(session_id=session_id, reason=reason)

    def list_workspace_tree(self, path: str = ".", max_depth: int = 3) -> List[Dict[str, Any]]:
        result = self._adapter.list_workspace_tree(path, max_depth)
        return result.get("items", [])

    def list_file_children(self, path: str = ".", limit: int = 200) -> List[Dict[str, Any]]:
        result = self._adapter.list_workspace_children(path, limit)
        return result.get("items", [])

    def read_file(self, path: str) -> Dict[str, Any]:
        return self._adapter.read_workspace_file(path)

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        return self._adapter.write_workspace_file(path, content)

    def list_artifacts(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._adapter.list_artifacts(limit=limit)

    def read_artifact(self, reference: str) -> Dict[str, Any]:
        return self._adapter.read_artifact(reference)

    def get_diff_preview(self, path: str, new_content: str) -> DiffPreview:
        old_content = ""
        try:
            file_data = self.read_file(path)
            old_content = file_data.get("content", "")
        except (OSError, ValueError):
            pass

        unified_diff = "".join(
            difflib.unified_diff(
                old_content.splitlines(True),
                new_content.splitlines(True),
                fromfile=path,
                tofile=path,
                lineterm="",
            )
        )

        return DiffPreview(
            path=path, old_content=old_content, new_content=new_content, unified_diff=unified_diff
        )

    def list_tasks(self, session_id: str = "") -> List[Dict[str, Any]]:
        result = self._adapter.list_tasks(session_id=session_id)
        return result.get("tasks", [])

    def get_session_plan(self, session_id: str) -> Optional[PlanSnapshot]:
        payload = self._adapter.get_session_plan(session_id)
        return payload

    def get_permission_context(self, session_id: str) -> PermissionContextView:
        return self._adapter.get_permission_context(session_id)

    def remember_permission_category(self, session_id: str, category: str) -> SessionSnapshot:
        return self._snapshot_to_protocol(
            self._adapter.remember_permission_category(session_id, category)
        )

    def get_tool_catalog(self) -> List[Dict[str, Any]]:
        return self._adapter.get_tool_catalog()

    def shutdown(self) -> None:
        """关闭 Core"""
        with self._lock:
            adapter = self._adapter
            self._adapter = None
            self._frontend = None
            self._callback_bridge = None
        if adapter is None:
            return
        shutdown = getattr(adapter, "shutdown", None)
        if callable(shutdown):
            try:
                shutdown()
            except (RuntimeError, ValueError, TypeError):
                return
            return
        list_sessions = getattr(adapter, "list_sessions", None)
        cancel_session = getattr(adapter, "cancel_session", None)
        if not callable(list_sessions) or not callable(cancel_session):
            return
        try:
            sessions = list_sessions(limit=1000)
        except (RuntimeError, ValueError, TypeError):
            return
        for item in list(sessions or []):
            if isinstance(item, dict):
                session_id = str(item.get("session_id") or "")
            else:
                session_id = str(getattr(item, "session_id", "") or "")
            if not session_id:
                continue
            try:
                cancel_session(session_id)
            except (RuntimeError, ValueError, TypeError):
                continue
