"""
Agent Core 适配器 - 实现 CoreInterface
将当前 InProcessAdapter / AgentRuntime 主链路包装为协议接口
"""

from __future__ import annotations

import difflib
import logging
import threading
from typing import Any, Dict, List, Optional

from embedagent_protocol import (
    CoreInterface,
    DiffPreview,
    FrontendCallbacks,
    PermissionContext,
    PlanSnapshot,
    RuntimeEnvironmentSnapshot,
    SessionEventEnvelope,
    SessionSnapshot,
    SessionStatus,
    WorkspaceInfo,
)

from embedagent.di_container import get_default_container

_LOGGER = logging.getLogger(__name__)


def get_inprocess_adapter(fresh: bool = False):
    """Return the InProcessAdapter class.

    Use fresh=True in tests to get an isolated reference.
    """
    return get_default_container().resolve("inprocess_adapter", fresh=fresh)


def _register_adapter_factory() -> None:
    from embedagent_host.inprocess_adapter import InProcessAdapter

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
        current_mode=str(snapshot.get("current_mode") or ""),
        created_at=snapshot.get("started_at", ""),
        updated_at=snapshot.get("updated_at", ""),
        workflow_state=dict(snapshot.get("workflow_state") or {}),
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
    )


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
        for key in ("context_manager",):
            if key in kwargs and kwargs.get(key) is not None:
                adapter_kwargs[key] = kwargs.get(key)
        self._adapter = AdapterClass(**adapter_kwargs)

    def attach_adapter(self, adapter) -> None:
        """Attach a hosted InProcessAdapter built outside this protocol wrapper."""
        self._adapter = adapter
        if adapter is not None:
            adapter.event_handler = self._on_adapter_event

    def register_frontend(self, frontend: FrontendCallbacks) -> None:
        """注册前端回调"""
        self._frontend = frontend

    def _on_adapter_event(self, envelope: SessionEventEnvelope) -> None:
        """Forward the canonical hosted event without reshaping it."""
        if self._frontend is not None:
            self._frontend.on_session_event(envelope)

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
            except (RuntimeError, ValueError, TypeError):
                _LOGGER.exception("Unhandled hosted session submission failure")

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

    def get_session_plan(self, session_id: str) -> Optional[PlanSnapshot]:
        payload = self._adapter.get_session_plan(session_id)
        return payload

    def get_permission_context(self, session_id: str) -> PermissionContext:
        return self._adapter.get_permission_context(session_id)

    def remember_permission_category(self, session_id: str, category: str) -> SessionSnapshot:
        return self._snapshot_to_protocol(
            self._adapter.remember_permission_category(session_id, category)
        )

    def shutdown(self) -> None:
        """关闭 Core"""
        with self._lock:
            adapter = self._adapter
            self._adapter = None
            self._frontend = None
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
