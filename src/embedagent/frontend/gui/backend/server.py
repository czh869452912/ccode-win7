"""
GUI Backend - FastAPI + WebSocket 服务
为 PyWebView 提供后端 API
"""

from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from embedagent.frontend.gui.backend.app_host import (
    GUIAppHost,
    NoActiveWorkspaceError,
    SingleWorkspaceAppHost,
)
from embedagent.frontend.gui.backend.app_shell import AppShellService
from embedagent.frontend.gui.backend.bridge import BlockingResult, ThreadsafeAsyncDispatcher
from embedagent.frontend.gui.backend.preview_service import PreviewService
from embedagent.frontend.gui.backend.session_events import build_session_event
from embedagent.frontend.gui.backend.source_control_service import SourceControlService
from embedagent.frontend.gui.backend.terminal_service import TerminalService
from embedagent.modes import DEFAULT_MODE
from embedagent.protocol import (
    CommandResult,
    CoreInterface,
    FrontendCallbacks,
    Message,
    PermissionRequest,
    PlanSnapshot,
    SessionSnapshot,
    ToolCall,
    ToolResult,
    UserInputRequest,
)

_LOGGER = logging.getLogger(__name__)


def _to_mapping(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    payload = getattr(value, "__dict__", None)
    if isinstance(payload, dict):
        return dict(payload)
    return None


def _read_value(payload: Any, key: str, default: Any = None, aliases: tuple = ()) -> Any:
    if isinstance(payload, dict):
        if key in payload:
            return payload.get(key, default)
        for alias in aliases:
            if alias in payload:
                return payload.get(alias, default)
        return default
    for name in (key,) + tuple(aliases):
        if hasattr(payload, name):
            return getattr(payload, name)
    return default


def _read_status_value(snapshot: Any) -> str:
    status = _read_value(snapshot, "status", "")
    return str(getattr(status, "value", status) or "")


def _serialize_session_snapshot(snapshot: Any) -> Dict[str, Any]:
    pending_permission = _to_mapping(_read_value(snapshot, "pending_permission"))
    pending_input = _to_mapping(
        _read_value(snapshot, "pending_input", None, aliases=("pending_user_input",))
    )
    pending_interaction = _to_mapping(_read_value(snapshot, "pending_interaction"))
    runtime_environment = _to_mapping(_read_value(snapshot, "runtime_environment"))
    has_pending_input = bool(
        _read_value(snapshot, "has_pending_input", False, aliases=("has_pending_user_input",))
    )
    pending_interaction_valid = _read_value(snapshot, "pending_interaction_valid", None)
    if pending_interaction_valid is None:
        pending_interaction_valid = bool(pending_interaction or pending_permission or pending_input)
    return {
        "session_id": str(_read_value(snapshot, "session_id", "") or ""),
        "status": _read_status_value(snapshot),
        "current_mode": str(_read_value(snapshot, "current_mode", DEFAULT_MODE) or DEFAULT_MODE),
        "started_at": str(_read_value(snapshot, "started_at", "", aliases=("created_at",)) or ""),
        "updated_at": str(_read_value(snapshot, "updated_at", "") or ""),
        "workflow_state": str(_read_value(snapshot, "workflow_state", "chat") or "chat"),
        "has_active_plan": bool(_read_value(snapshot, "has_active_plan", False)),
        "active_plan_ref": str(_read_value(snapshot, "active_plan_ref", "") or ""),
        "current_command_context": str(_read_value(snapshot, "current_command_context", "") or ""),
        "has_pending_permission": bool(_read_value(snapshot, "has_pending_permission", False)),
        "has_pending_input": has_pending_input,
        "pending_permission": pending_permission,
        "pending_user_input": pending_input,
        "pending_interaction": pending_interaction,
        "last_error": _read_value(snapshot, "last_error"),
        "runtime_source": str(_read_value(snapshot, "runtime_source", "") or ""),
        "bundled_tools_ready": bool(_read_value(snapshot, "bundled_tools_ready", False)),
        "fallback_warnings": list(_read_value(snapshot, "fallback_warnings", []) or []),
        "runtime_environment": runtime_environment,
        "compact_summary_text": str(_read_value(snapshot, "compact_summary_text", "") or ""),
        "context_analysis": dict(_read_value(snapshot, "context_analysis", {}) or {}),
        "compact_boundary_count": int(_read_value(snapshot, "compact_boundary_count", 0) or 0),
        "workspace_intelligence": list(_read_value(snapshot, "workspace_intelligence", []) or []),
        "context_pipeline_steps": list(_read_value(snapshot, "context_pipeline_steps", []) or []),
        "last_transition_reason": str(_read_value(snapshot, "last_transition_reason", "") or ""),
        "last_transition_message": str(_read_value(snapshot, "last_transition_message", "") or ""),
        "last_transition_display_reason": str(
            _read_value(snapshot, "last_transition_display_reason", "") or ""
        ),
        "recent_transition_reasons": list(
            _read_value(snapshot, "recent_transition_reasons", []) or []
        ),
        "recent_transitions": list(_read_value(snapshot, "recent_transitions", []) or []),
        "compact_retry_count": int(_read_value(snapshot, "compact_retry_count", 0) or 0),
        "pending_interaction_valid": bool(pending_interaction_valid),
        "restore_stop_reason": str(_read_value(snapshot, "restore_stop_reason", "") or ""),
        "restore_consumed_event_count": int(
            _read_value(snapshot, "restore_consumed_event_count", 0) or 0
        ),
        "restore_transcript_event_count": int(
            _read_value(snapshot, "restore_transcript_event_count", 0) or 0
        ),
        "operation_diagnostics": dict(_read_value(snapshot, "operation_diagnostics", {}) or {}),
        "runtime_config": dict(_read_value(snapshot, "runtime_config", {}) or {}),
        "compaction_state": dict(_read_value(snapshot, "compaction_state", {}) or {}),
        "recovery_state": dict(_read_value(snapshot, "recovery_state", {}) or {}),
        "current_phase": str(_read_value(snapshot, "current_phase", "") or ""),
        "discipline_profile": str(_read_value(snapshot, "discipline_profile", "") or ""),
        "current_activity": str(_read_value(snapshot, "current_activity", "") or ""),
        "task_summary": str(_read_value(snapshot, "task_summary", "") or ""),
        "task_items": list(_read_value(snapshot, "task_items", []) or []),
    }


def _tool_presentation_payload(source: Any) -> Dict[str, Any]:
    if not isinstance(source, dict):
        return {}
    data = source.get("data") if isinstance(source.get("data"), dict) else {}

    def pick(*keys: str) -> Any:
        for key in keys:
            if key in source and source.get(key) not in (None, ""):
                return source.get(key)
            if isinstance(data, dict) and key in data and data.get(key) not in (None, ""):
                return data.get(key)
        return ""

    return {
        "item_type": pick("item_type", "itemType"),
        "request_kind": pick("request_kind", "requestKind"),
        "tool_title": pick("tool_title", "toolTitle"),
        "tool_lifecycle_status": pick("tool_lifecycle_status", "toolLifecycleStatus", "status"),
        "command": pick("command"),
        "raw_command": pick("raw_command", "rawCommand"),
        "detail": pick("detail"),
        "source_activity_kind": pick("source_activity_kind", "sourceActivityKind"),
        "changed_files": pick("changed_files", "changedFiles") or [],
        "tool_data": pick("tool_data", "toolData", "item"),
    }


def _serialize_session_summary(payload: Any) -> Dict[str, Any]:
    data = dict(payload or {})
    thread = data.get("thread") if isinstance(data.get("thread"), dict) else {}
    safe_thread = {
        "title": str(thread.get("title") or ""),
        "archived": bool(thread.get("archived")),
        "archived_at": str(thread.get("archived_at") or ""),
        "forked_from": str(thread.get("forked_from") or ""),
        "forked_at": str(thread.get("forked_at") or ""),
    }
    return {
        "session_id": str(data.get("session_id") or ""),
        "title": str(data.get("title") or safe_thread.get("title") or ""),
        "current_mode": str(data.get("current_mode") or ""),
        "updated_at": str(data.get("updated_at") or ""),
        "summary_ref": str(data.get("summary_ref") or ""),
        "transcript_ref": str(data.get("transcript_ref") or ""),
        "thread": safe_thread,
    }


def _serialize_reload_signal_payload(session_id: str, payload: Any) -> Dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    status = str(data.get("status") or "reload_required")
    if status not in {"reload_required", "degraded"}:
        status = "reload_required"
    return {
        "session_id": str(data.get("session_id") or session_id or ""),
        "status": status,
        "first_seq": int(data.get("first_seq") or 0),
        "last_seq": int(data.get("last_seq") or 0),
        "reason": str(data.get("reason") or ""),
        "events": [],
    }


def _serialize_interaction_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    response = dict(payload or {})
    snapshot = response.get("snapshot")
    if snapshot is not None:
        response["snapshot"] = _serialize_session_snapshot(snapshot)
    return response


def _serialize_plan_snapshot(plan: Optional[PlanSnapshot]) -> Optional[Dict[str, Any]]:
    if plan is None:
        return None
    return {
        "session_id": plan.session_id,
        "title": plan.title,
        "content": plan.content,
        "updated_at": plan.updated_at,
        "workflow_state": plan.workflow_state,
        "path": plan.path,
        "summary": plan.summary,
    }


def _serialize_permission_context(context: Any) -> Dict[str, Any]:
    return {
        "session_id": str(_read_value(context, "session_id", "") or ""),
        "rules_path": str(_read_value(context, "rules_path", "") or ""),
        "categories": list(_read_value(context, "categories", []) or []),
        "rules": list(_read_value(context, "rules", []) or []),
        "remembered_categories": list(_read_value(context, "remembered_categories", []) or []),
        "auto_approve_all": bool(_read_value(context, "auto_approve_all", False)),
        "auto_approve_writes": bool(_read_value(context, "auto_approve_writes", False)),
        "auto_approve_commands": bool(_read_value(context, "auto_approve_commands", False)),
    }


def _translate_value_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip()
    if "session_id 不存在" in detail or detail == "session_not_found":
        return HTTPException(status_code=404, detail="session_not_found")
    if detail in ("interaction_gone", "interaction_expired", "未找到待处理的交互请求。"):
        return HTTPException(status_code=410, detail="interaction_expired")
    if detail == "interaction_conflict":
        return HTTPException(status_code=409, detail=detail)
    return HTTPException(status_code=422, detail=detail or "invalid_request")


def _thread_lifecycle_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip() or "thread_lifecycle_failed"
    if "session_id 不存在" in detail or detail == "session_not_found":
        return HTTPException(status_code=404, detail="session_not_found")
    if detail == "invalid_thread_title":
        return HTTPException(status_code=422, detail=detail)
    if detail == "session_fork_failed":
        return HTTPException(status_code=422, detail=detail)
    return HTTPException(status_code=422, detail=detail)


def _terminal_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip() or "terminal_failed"
    if detail == "terminal_not_found":
        return HTTPException(status_code=404, detail=detail)
    if detail == "terminal_not_running":
        return HTTPException(status_code=409, detail=detail)
    if detail in (
        "invalid_session_id",
        "invalid_terminal_id",
        "terminal_write_empty",
        "terminal_write_too_large",
        "terminal_cwd_outside_workspace",
        "terminal_cwd_not_found",
        "terminal_cwd_not_directory",
        "terminal_shell_unavailable",
    ):
        return HTTPException(status_code=422, detail=detail)
    if detail.startswith("terminal_start_failed"):
        return HTTPException(status_code=422, detail=detail)
    return HTTPException(status_code=422, detail=detail)


def _source_control_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip() or "source_control_failed"
    if detail in ("invalid_diff_scope", "path_outside_workspace"):
        return HTTPException(status_code=422, detail=detail)
    return HTTPException(status_code=422, detail=detail or "source_control_failed")


def _preview_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip() or "preview_failed"
    if detail == "preview_tab_not_found":
        return HTTPException(status_code=404, detail=detail)
    if detail in (
        "invalid_session_id",
        "invalid_preview_tab_id",
        "preview_url_required",
        "preview_url_too_long",
        "preview_url_not_local",
    ):
        return HTTPException(status_code=422, detail=detail)
    return HTTPException(status_code=422, detail=detail or "preview_failed")


class WebSocketFrontend(FrontendCallbacks):
    """
    WebSocket 前端适配器
    将 Core 的回调转换为 WebSocket 消息发送给前端
    """

    def __init__(self):
        self.connections: Set[WebSocket] = set()
        self._connections_lock = threading.RLock()
        self._pending_permissions = {}  # type: Dict[str, BlockingResult[bool]]
        self._pending_inputs = {}  # type: Dict[str, BlockingResult[Optional[Dict[str, Any]]]]
        self._pending_lock = threading.RLock()
        self._dispatcher = ThreadsafeAsyncDispatcher()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._dispatcher.bind_running_loop()
        with self._connections_lock:
            self.connections.add(websocket)
            total = len(self.connections)
        _LOGGER.info(f"WebSocket connected, total: {total}")

    def disconnect(self, websocket: WebSocket):
        with self._connections_lock:
            self.connections.discard(websocket)
            total = len(self.connections)
        _LOGGER.info(f"WebSocket disconnected, total: {total}")

    async def broadcast(self, message: Dict[str, Any]):
        """广播消息给所有连接的客户端"""
        disconnected = set()
        with self._connections_lock:
            connections = list(self.connections)
        for conn in connections:
            try:
                await conn.send_json(message)
            except (OSError, ValueError, TypeError):
                disconnected.add(conn)

        # 清理断开的连接
        if disconnected:
            with self._connections_lock:
                for conn in disconnected:
                    self.connections.discard(conn)

    def _dispatch_message(self, message: Dict[str, Any]) -> bool:
        result = self._dispatcher.dispatch(lambda: self.broadcast(message))
        if not result:
            _LOGGER.error("GUI event dispatch failed: %s", result.reason)
            return False
        return True

    # ============ FrontendCallbacks 实现 ============

    def on_message(self, message: Message) -> None:
        self._dispatch_message(
            {
                "type": "message",
                "data": {
                    "id": message.id,
                    "type": message.type.name,
                    "content": message.content,
                    "timestamp": message.timestamp.isoformat(),
                    "metadata": message.metadata,
                },
            }
        )

    def on_tool_start(self, call: ToolCall) -> None:
        arguments = {}
        if isinstance(call.arguments, dict):
            for key, value in call.arguments.items():
                if str(key).startswith("_"):
                    continue
                arguments[key] = value
        self._dispatch_message(
            {
                "type": "tool_start",
                "data": {
                    "tool_name": call.tool_name,
                    "arguments": arguments,
                    "call_id": call.call_id,
                    "turn_id": call.turn_id,
                    "step_id": call.step_id,
                    "step_index": call.step_index,
                    "tool_label": (
                        call.arguments.get("_tool_label")
                        if isinstance(call.arguments, dict)
                        else ""
                    ),
                    "permission_category": (
                        call.arguments.get("_permission_category")
                        if isinstance(call.arguments, dict)
                        else ""
                    ),
                    "supports_diff_preview": (
                        bool(call.arguments.get("_supports_diff_preview"))
                        if isinstance(call.arguments, dict)
                        else False
                    ),
                    "progress_renderer_key": (
                        call.arguments.get("_progress_renderer_key")
                        if isinstance(call.arguments, dict)
                        else ""
                    ),
                    "result_renderer_key": (
                        call.arguments.get("_result_renderer_key")
                        if isinstance(call.arguments, dict)
                        else ""
                    ),
                    "runtime_source": call.runtime_source,
                    "resolved_tool_roots": call.resolved_tool_roots,
                    **_tool_presentation_payload(call.arguments),
                },
            }
        )

    def on_tool_progress(self, call_id: str, progress: Dict[str, Any]) -> None:
        self._dispatch_message({"type": "tool_progress", "data": {"call_id": call_id, **progress}})

    def on_tool_finish(self, result: ToolResult) -> None:
        self._dispatch_message(
            {
                "type": "tool_finish",
                "data": {
                    "tool_name": result.tool_name,
                    "success": result.success,
                    "data": result.data,
                    "error": result.error,
                    "execution_time_ms": result.execution_time_ms,
                    "call_id": result.call_id,
                    "turn_id": result.turn_id,
                    "step_id": result.step_id,
                    "step_index": result.step_index,
                    "tool_label": (
                        result.data.get("tool_label") if isinstance(result.data, dict) else ""
                    ),
                    "permission_category": (
                        result.data.get("permission_category")
                        if isinstance(result.data, dict)
                        else ""
                    ),
                    "supports_diff_preview": (
                        bool(result.data.get("supports_diff_preview"))
                        if isinstance(result.data, dict)
                        else False
                    ),
                    "progress_renderer_key": (
                        result.data.get("progress_renderer_key")
                        if isinstance(result.data, dict)
                        else ""
                    ),
                    "result_renderer_key": (
                        result.data.get("result_renderer_key")
                        if isinstance(result.data, dict)
                        else ""
                    ),
                    "runtime_source": result.runtime_source
                    or (result.data.get("runtime_source") if isinstance(result.data, dict) else ""),
                    "resolved_tool_roots": result.resolved_tool_roots
                    or (
                        result.data.get("resolved_tool_roots")
                        if isinstance(result.data, dict)
                        else {}
                    ),
                    **_tool_presentation_payload(result.data),
                },
            }
        )

    def on_permission_request(self, request: PermissionRequest) -> bool:
        """同步阻塞等待用户响应"""
        waiter = BlockingResult(False)
        with self._pending_lock:
            self._pending_permissions[request.permission_id] = waiter
        queued = self._dispatch_message(
            {
                "type": "permission_request",
                "data": {
                    "permission_id": request.permission_id,
                    "session_id": request.session_id,
                    "tool_name": request.tool_name,
                    "category": request.category,
                    "reason": request.reason,
                    "details": request.details,
                    "turn_id": request.turn_id,
                    "step_id": request.step_id,
                    "step_index": request.step_index,
                },
            }
        )
        try:
            if not queued:
                return False
            return bool(waiter.wait(300.0))
        finally:
            with self._pending_lock:
                self._pending_permissions.pop(request.permission_id, None)

    def on_user_input_request(self, request: UserInputRequest) -> Optional[Dict[str, Any]]:
        """同步阻塞等待用户响应"""
        waiter = BlockingResult(None)  # type: BlockingResult[Optional[Dict[str, Any]]]
        with self._pending_lock:
            self._pending_inputs[request.request_id] = waiter
        queued = self._dispatch_message(
            {
                "type": "user_input_request",
                "data": {
                    "request_id": request.request_id,
                    "session_id": request.session_id,
                    "tool_name": request.tool_name,
                    "question": request.question,
                    "options": request.options,
                    "details": request.details,
                    "turn_id": request.turn_id,
                    "step_id": request.step_id,
                    "step_index": request.step_index,
                },
            }
        )
        try:
            if not queued:
                return None
            return waiter.wait(300.0)
        finally:
            with self._pending_lock:
                self._pending_inputs.pop(request.request_id, None)

    def on_session_status_change(self, snapshot: SessionSnapshot) -> None:
        snapshot_payload = _serialize_session_snapshot(snapshot)
        self._dispatch_message(
            {
                "type": "session_status",
                "data": {
                    "session_snapshot": snapshot_payload,
                    "session_id": snapshot_payload["session_id"],
                    "status": snapshot_payload["status"],
                    "current_mode": snapshot_payload["current_mode"],
                    "workflow_state": snapshot_payload["workflow_state"],
                    "has_active_plan": snapshot_payload["has_active_plan"],
                    "active_plan_ref": snapshot_payload["active_plan_ref"],
                    "current_command_context": snapshot_payload["current_command_context"],
                    "has_pending_permission": snapshot_payload["has_pending_permission"],
                    "has_pending_input": snapshot_payload["has_pending_input"],
                    "last_error": snapshot_payload["last_error"],
                    "runtime_source": snapshot_payload["runtime_source"],
                    "bundled_tools_ready": snapshot_payload["bundled_tools_ready"],
                    "fallback_warnings": snapshot_payload["fallback_warnings"],
                    "runtime_environment": snapshot_payload["runtime_environment"],
                    "pending_interaction_valid": snapshot_payload["pending_interaction_valid"],
                },
            }
        )

    def on_stream_delta(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self._dispatch_message({"type": "stream_delta", "data": {"text": text, **(metadata or {})}})

    def on_reasoning_delta(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self._dispatch_message(
            {"type": "reasoning_delta", "data": {"text": text, **(metadata or {})}}
        )

    def on_thinking_state_change(self, active: bool, reason: str = "") -> None:
        self._dispatch_message(
            {"type": "thinking_state", "data": {"active": active, "reason": reason}}
        )

    def on_command_result(self, result: CommandResult) -> None:
        self._dispatch_message(
            {
                "type": "command_result",
                "data": {
                    "command_name": result.command_name,
                    "success": result.success,
                    "message": result.message,
                    "data": result.data,
                    "turn_id": result.turn_id,
                    "step_id": result.step_id,
                    "step_index": result.step_index,
                },
            }
        )

    def on_plan_updated(self, plan: PlanSnapshot) -> None:
        self._dispatch_message(
            {
                "type": "plan_updated",
                "data": {
                    "plan": {
                        "session_id": plan.session_id,
                        "title": plan.title,
                        "content": plan.content,
                        "updated_at": plan.updated_at,
                        "workflow_state": plan.workflow_state,
                        "path": plan.path,
                        "summary": plan.summary,
                    }
                },
            }
        )

    def on_tasks_refresh(self) -> None:
        self._dispatch_message({"type": "tasks_refresh"})

    def on_artifacts_refresh(self) -> None:
        self._dispatch_message({"type": "artifacts_refresh"})

    def on_turn_event(self, event_name: str, payload: dict) -> None:
        session_id = str(payload.get("session_id") or "")
        self._dispatch_message(build_session_event(session_id, event_name, dict(payload)))

    # ============ 处理前端响应 ============

    def handle_permission_response(self, permission_id: str, approved: bool):
        """处理权限响应"""
        with self._pending_lock:
            waiter = self._pending_permissions.get(permission_id)
        if waiter is not None:
            waiter.resolve(bool(approved))
            return True
        return False

    def handle_user_input_response(self, request_id: str, payload: Dict[str, Any]):
        """处理用户输入响应"""
        with self._pending_lock:
            waiter = self._pending_inputs.get(request_id)
        if waiter is not None:
            waiter.resolve(dict(payload))
            return True
        return False

    def resolve_interaction_response(self, interaction_id: str, payload: Dict[str, Any]) -> bool:
        decision = bool((payload or {}).get("decision", False))
        if self.handle_permission_response(interaction_id, decision):
            return True
        if self.handle_user_input_response(interaction_id, dict(payload or {})):
            return True
        return False


class GUIBackend:
    """GUI 后端服务"""

    def __init__(
        self,
        core: Optional[CoreInterface] = None,
        static_dir: str = "",
        app_host: Optional[GUIAppHost] = None,
        host_diagnostics: Optional[Dict[str, Any]] = None,
        terminal_service: Optional[Any] = None,
        source_control_service: Optional[Any] = None,
        preview_service: Optional[Any] = None,
    ):
        if core is None and app_host is None:
            raise ValueError("core_or_app_host_required")
        self.static_dir = static_dir
        self.frontend = WebSocketFrontend()
        self.app_host = app_host if app_host is not None else SingleWorkspaceAppHost(core)
        self.app_host.bind_frontend(self.frontend)
        self.app_shell = AppShellService(
            self.app_host,
            host_diagnostics=host_diagnostics or {},
        )
        self.terminal_service = terminal_service
        self._terminal_service_injected = terminal_service is not None
        self._terminal_workspace_path = ""
        self.source_control_service = source_control_service
        self._source_control_service_injected = source_control_service is not None
        self._source_control_workspace_path = ""
        self.preview_service = preview_service
        self._preview_service_injected = preview_service is not None
        self._preview_workspace_path = ""
        if self.terminal_service is not None and hasattr(self.terminal_service, "set_event_sink"):
            self.terminal_service.set_event_sink(self._emit_terminal_event)
        self.app = self._create_app()
        self._current_session_id: Optional[str] = None

    def _call_core(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except NoActiveWorkspaceError:
            raise HTTPException(status_code=409, detail="no_active_workspace")
        except ValueError as exc:
            raise _translate_value_error(exc)

    def _require_core(self) -> CoreInterface:
        try:
            return self.app_host.require_core()
        except NoActiveWorkspaceError:
            raise HTTPException(status_code=409, detail="no_active_workspace")

    def _terminal(self) -> Any:
        self._require_core()
        host_state = self.app_host.bootstrap()
        active_workspace = (
            host_state.get("active_workspace") if isinstance(host_state, dict) else None
        )
        workspace_path = ""
        if isinstance(active_workspace, dict):
            workspace_path = str(active_workspace.get("path") or "")
        if not workspace_path:
            raise HTTPException(status_code=409, detail="no_active_workspace")
        real_workspace = os.path.realpath(workspace_path)
        if (
            self.terminal_service is not None
            and not self._terminal_service_injected
            and self._terminal_workspace_path
            and real_workspace != self._terminal_workspace_path
        ):
            self.terminal_service.shutdown()
            self.terminal_service = None
        if self.terminal_service is None:
            self._terminal_workspace_path = real_workspace
            self.terminal_service = TerminalService(
                workspace_root=workspace_path,
                event_sink=self._emit_terminal_event,
            )
        return self.terminal_service

    def _active_workspace_path(self) -> str:
        self._require_core()
        host_state = self.app_host.bootstrap()
        active_workspace = (
            host_state.get("active_workspace") if isinstance(host_state, dict) else None
        )
        workspace_path = ""
        if isinstance(active_workspace, dict):
            workspace_path = str(active_workspace.get("path") or "")
        if not workspace_path:
            raise HTTPException(status_code=409, detail="no_active_workspace")
        return os.path.realpath(workspace_path)

    def _source_control(self) -> Any:
        real_workspace = self._active_workspace_path()
        if (
            self.source_control_service is not None
            and not self._source_control_service_injected
            and self._source_control_workspace_path
            and real_workspace != self._source_control_workspace_path
        ):
            self.source_control_service = None
        if self.source_control_service is None:
            self._source_control_workspace_path = real_workspace
            self.source_control_service = SourceControlService(workspace_root=real_workspace)
        return self.source_control_service

    def _preview(self) -> Any:
        if self.preview_service is not None and self._preview_service_injected:
            return self.preview_service
        real_workspace = self._active_workspace_path()
        if (
            self.preview_service is not None
            and self._preview_workspace_path
            and real_workspace != self._preview_workspace_path
        ):
            self.preview_service = None
        if self.preview_service is None:
            self._preview_workspace_path = real_workspace
            self.preview_service = PreviewService(workspace_root=real_workspace)
        return self.preview_service

    def _emit_terminal_event(self, event: Dict[str, Any]) -> None:
        self.frontend._dispatch_message({"type": "terminal_event", "data": {"event": dict(event)}})

    def _wait_for_interaction_resolution(
        self, session_id: str, interaction_id: str, timeout_seconds: float = 2.0
    ):
        deadline = time.time() + max(timeout_seconds, 0.0)
        latest = None
        while time.time() < deadline:
            core = self._require_core()
            latest = self._call_core(core.get_session_snapshot, session_id)
            pending = _to_mapping(_read_value(latest, "pending_interaction"))
            pending_id = str((pending or {}).get("interaction_id") or "").strip()
            if not pending_id or pending_id != str(interaction_id or "").strip():
                return latest
            time.sleep(0.02)
        if latest is not None:
            return latest
        core = self._require_core()
        return self._call_core(core.get_session_snapshot, session_id)

    def _create_app(self) -> FastAPI:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            _LOGGER.info("GUI Backend starting...")
            yield
            _LOGGER.info("GUI Backend shutting down...")
            if self.terminal_service is not None:
                self.terminal_service.shutdown()
            self.app_host.shutdown()

        app = FastAPI(title="EmbedAgent GUI", lifespan=lifespan)

        # 静态文件
        app.mount("/static", StaticFiles(directory=self.static_dir), name="static")

        # 根路由
        @app.get("/")
        async def root():
            return FileResponse(f"{self.static_dir}/index.html")

        @app.get("/api/app/bootstrap")
        async def get_app_bootstrap():
            return self.app_shell.bootstrap()

        @app.get("/api/app/workspaces")
        async def list_app_workspaces():
            return self.app_shell.list_workspaces()

        @app.post("/api/app/workspaces")
        async def open_app_workspace(request: Dict[str, Any]):
            path = str(request.get("path") or "").strip()
            label = str(request.get("label") or "").strip()
            if not path:
                raise HTTPException(status_code=422, detail="workspace_path_required")
            try:
                return self.app_shell.open_workspace_path(path, label=label)
            except ValueError as exc:
                detail = str(exc or "").strip() or "workspace_open_failed"
                status = 404 if detail == "workspace_not_found" else 422
                raise HTTPException(status_code=status, detail=detail)

        @app.post("/api/app/workspaces/{workspace_id}/activate")
        async def activate_app_workspace(workspace_id: str):
            try:
                return self.app_shell.activate_workspace(workspace_id)
            except ValueError as exc:
                detail = str(exc or "").strip() or "workspace_activate_failed"
                status = 404 if detail == "workspace_not_found" else 422
                raise HTTPException(status_code=status, detail=detail)

        @app.delete("/api/app/workspaces/{workspace_id}")
        async def remove_app_workspace(workspace_id: str):
            return self.app_shell.remove_workspace(workspace_id)

        @app.get("/api/app/source-control/status")
        async def get_source_control_status():
            source_control = self._source_control()
            return {"source_control": source_control.status()}

        @app.post("/api/app/source-control/refresh")
        async def refresh_source_control_status():
            source_control = self._source_control()
            return {"source_control": source_control.status()}

        @app.get("/api/app/source-control/diff")
        async def get_source_control_diff(path: str, scope: str = "unstaged"):
            source_control = self._source_control()
            try:
                payload = source_control.diff(path, scope=scope)
            except ValueError as exc:
                raise _source_control_http_error(exc)
            return {"diff": payload}

        @app.post("/api/app/preview/open-external")
        async def open_preview_external(request: Dict[str, Any]):
            preview = self._preview()
            try:
                payload = preview.open_external(str(request.get("url") or ""))
            except ValueError as exc:
                raise _preview_http_error(exc)
            return payload

        # API 路由
        @app.get("/api/sessions")
        async def list_sessions(limit: int = 10):
            core = self._require_core()
            return {"sessions": core.list_sessions(limit)}

        @app.get("/api/sessions/{session_id}")
        async def get_session_snapshot(session_id: str):
            core = self._require_core()
            snapshot = self._call_core(core.get_session_snapshot, session_id)
            return _serialize_session_snapshot(snapshot)

        @app.get("/api/sessions/{session_id}/bootstrap")
        async def get_session_bootstrap(session_id: str):
            core = self._require_core()
            payload = self._call_core(core.get_session_bootstrap, session_id)
            return {
                "snapshot": _serialize_session_snapshot(payload.get("snapshot")),
                "history": dict(payload.get("history") or {}),
                "plan": _serialize_plan_snapshot(payload.get("plan")),
                "permission_context": _serialize_permission_context(
                    payload.get("permission_context")
                ),
            }

        @app.post("/api/sessions")
        async def create_session(mode: str = DEFAULT_MODE):
            core = self._require_core()
            snapshot = self._call_core(core.create_session, mode)
            self._current_session_id = str(_read_value(snapshot, "session_id", "") or "")
            return _serialize_session_snapshot(snapshot)

        @app.post("/api/sessions/{session_id}/resume")
        async def resume_session(session_id: str, mode: str = ""):
            core = self._require_core()
            snapshot = self._call_core(core.resume_session, session_id, mode)
            self._current_session_id = str(_read_value(snapshot, "session_id", "") or "")
            return _serialize_session_snapshot(snapshot)

        @app.post("/api/sessions/{session_id}/rename")
        async def rename_session(session_id: str, request: Dict[str, Any]):
            core = self._require_core()
            try:
                summary = core.rename_session(
                    session_id,
                    str(request.get("title") or ""),
                )
            except ValueError as exc:
                raise _thread_lifecycle_http_error(exc)
            return {"session": _serialize_session_summary(summary)}

        @app.post("/api/sessions/{session_id}/archive")
        async def archive_session(session_id: str):
            core = self._require_core()
            try:
                summary = core.archive_session(session_id)
            except ValueError as exc:
                raise _thread_lifecycle_http_error(exc)
            return {"session": _serialize_session_summary(summary)}

        @app.post("/api/sessions/{session_id}/fork")
        async def fork_session(session_id: str, request: Dict[str, Any]):
            core = self._require_core()
            try:
                summary = core.fork_session(
                    session_id,
                    str(request.get("title") or ""),
                )
            except ValueError as exc:
                raise _thread_lifecycle_http_error(exc)
            payload = _serialize_session_summary(summary)
            return {"session_id": payload["session_id"], "session": payload}

        @app.get("/api/sessions/{session_id}/preview")
        async def list_preview_sessions(session_id: str):
            preview = self._preview()
            try:
                payload = preview.list_sessions(session_id)
            except ValueError as exc:
                raise _preview_http_error(exc)
            return {"preview": payload}

        @app.post("/api/sessions/{session_id}/preview/open")
        async def open_preview(session_id: str, request: Dict[str, Any]):
            preview = self._preview()
            try:
                payload = preview.open(session_id, str(request.get("url") or ""))
            except ValueError as exc:
                raise _preview_http_error(exc)
            return {"preview": payload}

        @app.post("/api/sessions/{session_id}/preview/{tab_id}/refresh")
        async def refresh_preview(session_id: str, tab_id: str):
            preview = self._preview()
            try:
                payload = preview.refresh(session_id, tab_id)
            except ValueError as exc:
                raise _preview_http_error(exc)
            return {"preview": payload}

        @app.post("/api/sessions/{session_id}/preview/{tab_id}/close")
        async def close_preview(session_id: str, tab_id: str):
            preview = self._preview()
            try:
                payload = preview.close(session_id, tab_id)
            except ValueError as exc:
                raise _preview_http_error(exc)
            return {"preview": payload}

        @app.get("/api/sessions/{session_id}/terminals")
        async def list_session_terminals(session_id: str):
            terminal = self._terminal()
            return {"terminals": terminal.list_sessions(session_id)}

        @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/open")
        async def open_terminal(session_id: str, terminal_id: str, request: Dict[str, Any]):
            terminal = self._terminal()
            try:
                snapshot = terminal.open_or_attach(
                    session_id,
                    terminal_id,
                    cwd=str(request.get("cwd") or ""),
                    cols=int(request.get("cols") or 80),
                    rows=int(request.get("rows") or 24),
                )
            except ValueError as exc:
                raise _terminal_http_error(exc)
            return {"terminal": snapshot}

        @app.get("/api/sessions/{session_id}/terminals/{terminal_id}/snapshot")
        async def get_terminal_snapshot(session_id: str, terminal_id: str):
            terminal = self._terminal()
            try:
                snapshot = terminal.snapshot(session_id, terminal_id)
            except ValueError as exc:
                raise _terminal_http_error(exc)
            return {"terminal": snapshot}

        @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/write")
        async def write_terminal(session_id: str, terminal_id: str, request: Dict[str, Any]):
            terminal = self._terminal()
            try:
                snapshot = terminal.write(session_id, terminal_id, str(request.get("data") or ""))
            except ValueError as exc:
                raise _terminal_http_error(exc)
            return {"terminal": snapshot}

        @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/clear")
        async def clear_terminal(session_id: str, terminal_id: str):
            terminal = self._terminal()
            try:
                snapshot = terminal.clear(session_id, terminal_id)
            except ValueError as exc:
                raise _terminal_http_error(exc)
            return {"terminal": snapshot}

        @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/restart")
        async def restart_terminal(session_id: str, terminal_id: str, request: Dict[str, Any]):
            terminal = self._terminal()
            try:
                snapshot = terminal.restart(
                    session_id,
                    terminal_id,
                    cwd=str(request.get("cwd") or ""),
                    cols=int(request.get("cols") or 80),
                    rows=int(request.get("rows") or 24),
                )
            except ValueError as exc:
                raise _terminal_http_error(exc)
            return {"terminal": snapshot}

        @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/resize")
        async def resize_terminal(session_id: str, terminal_id: str, request: Dict[str, Any]):
            terminal = self._terminal()
            try:
                snapshot = terminal.resize(
                    session_id,
                    terminal_id,
                    cols=int(request.get("cols") or 80),
                    rows=int(request.get("rows") or 24),
                )
            except ValueError as exc:
                raise _terminal_http_error(exc)
            return {"terminal": snapshot}

        @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/close")
        async def close_terminal(session_id: str, terminal_id: str):
            terminal = self._terminal()
            try:
                snapshot = terminal.close(session_id, terminal_id)
            except ValueError as exc:
                raise _terminal_http_error(exc)
            return {"terminal": snapshot}

        @app.post("/api/sessions/{session_id}/message")
        async def send_message(session_id: str, request: Dict[str, Any]):
            text = request.get("text", "")
            self._current_session_id = session_id
            core = self._require_core()
            self._call_core(core.submit_message, session_id, text)
            return {"status": "submitted"}

        @app.post("/api/sessions/{session_id}/cancel")
        async def cancel_session(session_id: str):
            core = self._require_core()
            self._call_core(core.cancel_session, session_id)
            return {"status": "cancelled"}

        @app.post("/api/sessions/{session_id}/mode")
        async def set_mode(session_id: str, request: Dict[str, Any]):
            mode = request.get("mode", DEFAULT_MODE)
            core = self._require_core()
            self._call_core(core.set_mode, session_id, mode)
            return {"status": "ok"}

        @app.post("/api/sessions/{session_id}/interactions/{interaction_id}/respond")
        async def respond_to_interaction(
            session_id: str, interaction_id: str, request: Dict[str, Any]
        ):
            self._current_session_id = session_id
            if self.frontend.resolve_interaction_response(interaction_id, request):
                if bool(request.get("decision")) and bool(request.get("remember")):
                    category = str(request.get("category") or "").strip()
                    if category:
                        core = self._require_core()
                        remember_method = getattr(core, "remember_permission_category", None)
                        if callable(remember_method):
                            self._call_core(remember_method, session_id, category)
                snapshot = self._wait_for_interaction_resolution(session_id, interaction_id)
                return _serialize_interaction_response(
                    {
                        "session_id": session_id,
                        "interaction_id": interaction_id,
                        "status": "resolved",
                        "snapshot": snapshot,
                    }
                )
            core = self._require_core()
            response = self._call_core(
                core.respond_to_interaction, session_id, interaction_id, request
            )
            if bool(request.get("decision")) and bool(request.get("remember")):
                category = str(request.get("category") or "").strip()
                if category:
                    remember_method = getattr(core, "remember_permission_category", None)
                    if callable(remember_method):
                        self._call_core(remember_method, session_id, category)
            return _serialize_interaction_response(response)

        @app.get("/api/workspace")
        async def get_workspace():
            core = self._require_core()
            return core.get_workspace_snapshot()

        @app.get("/api/workspace/recipes")
        async def get_workspace_recipes():
            core = self._require_core()
            return core.list_workspace_recipes()

        @app.post("/api/sessions/{session_id}/resources/reload")
        async def reload_session_resources(session_id: str):
            core = self._require_core()
            return self._call_core(core.reload_resources, session_id, reason="api")

        @app.get("/api/tool-catalog")
        async def get_tool_catalog():
            core = self._require_core()
            return {"items": core.get_tool_catalog()}

        @app.get("/api/sessions/{session_id}/plan")
        async def get_session_plan(session_id: str):
            core = self._require_core()
            plan = self._call_core(core.get_session_plan, session_id)
            if plan is None:
                return {"plan": None}
            return {"plan": _serialize_plan_snapshot(plan)}

        @app.get("/api/sessions/{session_id}/permissions")
        async def get_permission_context(session_id: str):
            core = self._require_core()
            context = self._call_core(core.get_permission_context, session_id)
            return _serialize_permission_context(context)

        @app.get("/api/sessions/{session_id}/events")
        async def get_session_events(session_id: str, after_seq: int = 0, limit: int = 200):
            core = self._require_core()
            payload = self._call_core(
                core.load_session_events_after, session_id, after_seq, limit=limit
            )
            return _serialize_reload_signal_payload(session_id, payload)

        @app.get("/api/files")
        async def list_workspace_tree(path: str = ".", max_depth: int = 3):
            core = self._require_core()
            return {"items": core.list_workspace_tree(path, max_depth)}

        @app.get("/api/files/tree")
        async def list_file_children(path: str = ".", limit: int = 200):
            core = self._require_core()
            return {"items": core.list_file_children(path, limit)}

        @app.get("/api/files/{path:path}")
        async def read_file(path: str):
            try:
                core = self._require_core()
                return core.read_file(path)
            except HTTPException:
                raise
            except (OSError, ValueError, TypeError) as e:
                return {"error": str(e)}

        @app.post("/api/files/{path:path}")
        async def write_file(path: str, request: Dict[str, Any]):
            raise HTTPException(status_code=405, detail="file_write_disabled")

        @app.post("/api/diff")
        async def get_diff(request: Dict[str, Any]):
            path = request.get("path", "")
            new_content = request.get("new_content", "")
            core = self._require_core()
            diff = core.get_diff_preview(path, new_content)
            return {
                "path": diff.path,
                "old_content": diff.old_content,
                "new_content": diff.new_content,
                "unified_diff": diff.unified_diff,
            }

        @app.get("/api/tasks")
        async def list_tasks(session_id: str = ""):
            core = self._require_core()
            return {"tasks": core.list_tasks(session_id=session_id)}

        @app.get("/api/artifacts")
        async def list_artifacts(limit: int = 20):
            core = self._require_core()
            return {"items": core.list_artifacts(limit=limit)}

        @app.get("/api/artifacts/{reference:path}")
        async def read_artifact(reference: str):
            core = self._require_core()
            return core.read_artifact(reference)

        # WebSocket 路由
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.frontend.connect(websocket)
            try:
                while True:
                    data = await websocket.receive_json()
                    await self._handle_websocket_message(data)
            except WebSocketDisconnect:
                _LOGGER.info("WebSocket client disconnected")
            except (OSError, ValueError, TypeError, RuntimeError):
                _LOGGER.exception("Unhandled websocket failure")
            finally:
                self.frontend.disconnect(websocket)

        return app

    async def _handle_websocket_message(self, data: Dict[str, Any]):
        """处理 WebSocket 消息"""
        msg_type = data.get("type")

        if msg_type == "permission_response":
            perm_id = data.get("permission_id", "")
            approved = data.get("approved", False)
            remember = bool(data.get("remember", False))
            category = str(data.get("category") or "")
            session_id = str(data.get("session_id") or "")
            if (
                remember
                and approved
                and category
                and self._current_session_id
                and session_id == self._current_session_id
            ):
                try:
                    core = self._require_core()
                except HTTPException:
                    core = None
                if core is not None:
                    remember_method = getattr(core, "remember_permission_category", None)
                    if callable(remember_method):
                        remember_method(self._current_session_id, category)
            self.frontend.handle_permission_response(perm_id, approved)

        elif msg_type == "user_input_response":
            req_id = data.get("request_id", "")
            self.frontend.handle_user_input_response(req_id, data)
