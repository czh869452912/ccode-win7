"""
Agent Core 适配器 - 实现 CoreInterface
将现有的 AgentLoop 包装为协议接口
"""
from __future__ import annotations

import difflib
import os
import threading
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

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
    SessionSnapshot,
    SessionStatus,
    ToolCall,
    ToolResult,
    UserInputRequest,
    WorkspaceInfo,
)

# 延迟导入现有实现，避免循环依赖
_inprocess_adapter = None

def _get_adapter_class():
    global _inprocess_adapter
    if _inprocess_adapter is None:
        from embedagent.inprocess_adapter import InProcessAdapter
        _inprocess_adapter = InProcessAdapter
    return _inprocess_adapter


class CallbackBridge:
    """回调桥接器 - 将 callback 转换为 Protocol 类型"""
    
    def __init__(self, frontend: FrontendCallbacks):
        self.frontend = frontend
        self._pending_permissions: Dict[str, threading.Event] = {}
        self._pending_permission_results: Dict[str, bool] = {}
        self._pending_inputs: Dict[str, threading.Event] = {}
        self._pending_input_results: Dict[str, Optional[str]] = {}
    
    def emit(self, event_name: str, session_id: str, payload: Dict[str, Any]) -> None:
        """处理来自 Adapter 的事件"""
        if event_name == "assistant_delta":
            self.frontend.on_stream_delta(payload.get("text", ""))
            
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
            call = ToolCall(
                tool_name=payload.get("tool_name", ""),
                arguments=arguments,
                call_id=str(payload.get("call_id") or str(uuid.uuid4())[:8])
            )
            self.frontend.on_tool_start(call)
            
        elif event_name == "tool_finished":
            result = ToolResult(
                tool_name=payload.get("tool_name", ""),
                success=payload.get("success", False),
                data=payload.get("data", {}),
                error=payload.get("error"),
                call_id=str(payload.get("call_id") or ""),
            )
            self.frontend.on_tool_finish(result)
            
        elif event_name == "session_error":
            snapshot = payload.get("session_snapshot", {})
            if isinstance(snapshot, dict) and snapshot.get("session_id"):
                self._notify_status_change(snapshot)
            msg = Message(
                id=str(uuid.uuid4()),
                type=MessageType.ERROR,
                content=payload.get("error", "Unknown error")
            )
            self.frontend.on_message(msg)

        elif event_name == "session_status":
            snapshot = payload.get("session_snapshot", {})
            if isinstance(snapshot, dict):
                self._notify_status_change(snapshot)

        elif event_name == "reasoning_delta":
            self.frontend.on_reasoning_delta(payload.get("text", ""))

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
            
        elif event_name in ("turn_start", "turn_end"):
            if hasattr(self.frontend, "on_turn_event"):
                self.frontend.on_turn_event(event_name, payload)

        elif event_name == "mode_changed":
            snapshot = payload.get("session_snapshot", {})
            if isinstance(snapshot, dict) and snapshot.get("session_id"):
                self._notify_status_change(snapshot)

        elif event_name == "context_compacted":
            stats = payload.get("recent_turns", 0)
            msg = Message(
                id=str(uuid.uuid4()),
                type=MessageType.CONTEXT_COMPACTED,
                content=f"Context compacted: {stats} turns kept"
            )
            self.frontend.on_message(msg)

    def request_permission(self, payload: Dict[str, Any]) -> bool:
        request = PermissionRequest(
            permission_id=str(payload.get("permission_id", "")),
            tool_name=str(payload.get("tool_name", "")),
            category=str(payload.get("category", "")),
            reason=str(payload.get("reason", "")),
            details=payload.get("details", {}),
        )
        return bool(self.frontend.on_permission_request(request))

    def request_user_input(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        request = UserInputRequest(
            request_id=str(payload.get("request_id", "")),
            tool_name=str(payload.get("tool_name", "")),
            question=str(payload.get("question", "")),
            options=payload.get("options", []),
        )
        answer = self.frontend.on_user_input_request(request)
        if answer is None:
            return None
        if isinstance(answer, dict):
            return answer
        return {"answer": str(answer)}
    
    def _notify_status_change(self, snapshot: Dict[str, Any]) -> None:
        """通知状态变化"""
        status_map = {
            "idle": SessionStatus.IDLE,
            "running": SessionStatus.RUNNING,
            "waiting_permission": SessionStatus.WAITING_PERMISSION,
            "waiting_user_input": SessionStatus.WAITING_INPUT,
            "error": SessionStatus.ERROR
        }
        
        pending_perm = None
        if snapshot.get("has_pending_permission"):
            permission = snapshot.get("pending_permission", {})
            if isinstance(permission, dict):
                pending_perm = PermissionRequest(
                    permission_id=permission.get("permission_id", ""),
                    tool_name=permission.get("tool_name", ""),
                    category=permission.get("category", ""),
                    reason=permission.get("reason", ""),
                    details=permission.get("details", {}),
                )

        pending_input = None
        if snapshot.get("has_pending_user_input") or snapshot.get("has_pending_input"):
            request = snapshot.get("pending_user_input", {})
            if isinstance(request, dict):
                pending_input = UserInputRequest(
                    request_id=request.get("request_id", ""),
                    tool_name=request.get("tool_name", ""),
                    question=request.get("question", ""),
                    options=request.get("options", []),
                )

        snap = SessionSnapshot(
            session_id=snapshot.get("session_id", ""),
            status=status_map.get(snapshot.get("status"), SessionStatus.IDLE),
            current_mode=snapshot.get("current_mode", "code"),
            created_at=snapshot.get("started_at", ""),
            updated_at=snapshot.get("updated_at", ""),
            workflow_state=snapshot.get("workflow_state", "chat"),
            has_active_plan=bool(snapshot.get("has_active_plan", False)),
            active_plan_ref=snapshot.get("active_plan_ref", ""),
            current_command_context=snapshot.get("current_command_context", ""),
            has_pending_permission=bool(snapshot.get("has_pending_permission", False)),
            has_pending_input=bool(snapshot.get("has_pending_user_input", snapshot.get("has_pending_input", False))),
            pending_permission=pending_perm,
            pending_input=pending_input,
            last_error=snapshot.get("last_error"),
        )
        self.frontend.on_session_status_change(snap)


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
        AdapterClass = _get_adapter_class()
        adapter_kwargs = {
            "client": client,
            "tools": tools,
            "max_turns": kwargs.get("max_turns", 8),
            "permission_policy": kwargs.get("permission_policy"),
            "event_handler": self._on_adapter_event,
        }
        for key in (
            "summary_store",
            "project_memory_store",
            "context_manager",
            "memory_maintenance",
            "timeline_store",
            "maintenance_interval",
        ):
            if key in kwargs and kwargs.get(key) is not None:
                adapter_kwargs[key] = kwargs.get(key)
        self._adapter = AdapterClass(**adapter_kwargs)
    
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
        status_map = {
            "idle": SessionStatus.IDLE,
            "running": SessionStatus.RUNNING,
            "waiting_permission": SessionStatus.WAITING_PERMISSION,
            "waiting_user_input": SessionStatus.WAITING_INPUT,
            "error": SessionStatus.ERROR
        }
        
        pending_perm = None
        if snapshot.get("has_pending_permission"):
            p = snapshot.get("pending_permission", {})
            pending_perm = PermissionRequest(
                permission_id=p.get("permission_id", ""),
                tool_name=p.get("tool_name", ""),
                category=p.get("category", ""),
                reason=p.get("reason", ""),
                details=p.get("details", {})
            )
        
        pending_input = None
        if snapshot.get("has_pending_user_input") or snapshot.get("has_pending_input"):
            i = snapshot.get("pending_user_input", {})
            pending_input = UserInputRequest(
                request_id=i.get("request_id", ""),
                tool_name=i.get("tool_name", ""),
                question=i.get("question", ""),
                options=i.get("options", [])
            )
        
        return SessionSnapshot(
            session_id=snapshot.get("session_id", ""),
            status=status_map.get(snapshot.get("status"), SessionStatus.IDLE),
            current_mode=snapshot.get("current_mode", "code"),
            created_at=snapshot.get("started_at", ""),
            updated_at=snapshot.get("updated_at", ""),
            workflow_state=snapshot.get("workflow_state", "chat"),
            has_active_plan=bool(snapshot.get("has_active_plan", False)),
            active_plan_ref=snapshot.get("active_plan_ref", ""),
            current_command_context=snapshot.get("current_command_context", ""),
            has_pending_permission=snapshot.get("has_pending_permission", False),
            has_pending_input=snapshot.get("has_pending_user_input", snapshot.get("has_pending_input", False)),
            pending_permission=pending_perm,
            pending_input=pending_input,
            last_error=snapshot.get("last_error")
        )
    
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
    
    def submit_message(self, session_id: str, text: str) -> None:
        """异步提交消息"""
        def run():
            try:
                self._adapter.submit_user_message(
                    session_id=session_id,
                    text=text,
                    stream=True,
                    wait=True,
                    permission_resolver=self._resolve_permission,
                    user_input_resolver=self._resolve_user_input,
                    event_handler=self._on_adapter_event
                )
            except Exception as e:
                if self._frontend:
                    self._frontend.on_message(Message(
                        id=str(uuid.uuid4()),
                        type=MessageType.ERROR,
                        content=str(e)
                    ))
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def _resolve_permission(self, payload: Dict[str, Any]) -> bool:
        if self._callback_bridge is None:
            return False
        return self._callback_bridge.request_permission(payload)

    def _resolve_user_input(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self._callback_bridge is None:
            return None
        return self._callback_bridge.request_user_input(payload)
    
    def cancel_session(self, session_id: str) -> None:
        self._adapter.cancel_session(session_id)
    
    def set_mode(self, session_id: str, mode: str) -> None:
        self._adapter.set_session_mode(session_id, mode)
    
    def approve_permission(self, session_id: str, permission_id: str) -> None:
        self._adapter.approve_permission(session_id, permission_id)
    
    def reject_permission(self, session_id: str, permission_id: str) -> None:
        self._adapter.reject_permission(session_id, permission_id)
    
    def reply_user_input(self, session_id: str, request_id: str,
                        answer: str, **kwargs) -> None:
        self._adapter.reply_user_input(
            session_id, request_id, answer,
            selected_index=kwargs.get("selected_index"),
            selected_mode=kwargs.get("selected_mode"),
            selected_option_text=kwargs.get("selected_option_text")
        )
    
    def get_workspace_snapshot(self) -> WorkspaceInfo:
        snapshot = self._adapter.get_workspace_snapshot()
        git_info = snapshot.get("git", {})
        tree_info = snapshot.get("tree", {})
        return WorkspaceInfo(
            path=snapshot.get("workspace", ""),
            git_branch=git_info.get("branch", ""),
            git_dirty=git_info.get("dirty_count", 0),
            file_count=tree_info.get("file_count", 0),
            dir_count=tree_info.get("dir_count", 0)
        )
    
    def list_files(self, path: str = ".", max_depth: int = 3) -> List[Dict[str, Any]]:
        result = self._adapter.list_workspace_tree(path, max_depth)
        return result.get("items", [])

    def list_file_children(self, path: str = ".", limit: int = 200) -> List[Dict[str, Any]]:
        result = self._adapter.list_workspace_children(path, limit)
        return result.get("items", [])
    
    def read_file(self, path: str) -> Dict[str, Any]:
        return self._adapter.read_workspace_file(path)
    
    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        return self._adapter.write_workspace_file(path, content)

    def get_session_timeline(self, session_id: str, limit: int = 200) -> Dict[str, Any]:
        return self._adapter.get_session_timeline(session_id, limit=limit)

    def list_artifacts(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._adapter.list_artifacts(limit=limit)

    def read_artifact(self, reference: str) -> Dict[str, Any]:
        return self._adapter.read_artifact(reference)
    
    def get_diff_preview(self, path: str, new_content: str) -> DiffPreview:
        old_content = ""
        try:
            file_data = self.read_file(path)
            old_content = file_data.get("content", "")
        except:
            pass
        
        unified_diff = "".join(difflib.unified_diff(
            old_content.splitlines(True),
            new_content.splitlines(True),
            fromfile=path,
            tofile=path,
            lineterm=""
        ))
        
        return DiffPreview(
            path=path,
            old_content=old_content,
            new_content=new_content,
            unified_diff=unified_diff
        )
    
    def list_todos(self, session_id: str = "") -> List[Dict[str, Any]]:
        result = self._adapter.list_todos(session_id=session_id)
        return result.get("todos", [])

    def get_session_plan(self, session_id: str) -> Optional[PlanSnapshot]:
        payload = self._adapter.get_session_plan(session_id)
        return payload

    def get_permission_context(self, session_id: str) -> PermissionContextView:
        return self._adapter.get_permission_context(session_id)

    def remember_permission_category(self, session_id: str, category: str) -> SessionSnapshot:
        return self._snapshot_to_protocol(
            self._adapter.remember_permission_category(session_id, category)
        )
    
    def shutdown(self) -> None:
        """关闭 Core"""
        # 清理资源
        pass
