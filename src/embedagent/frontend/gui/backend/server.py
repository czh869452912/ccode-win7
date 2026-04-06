"""
GUI Backend - FastAPI + WebSocket 服务
为 PyWebView 提供后端 API
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from embedagent.frontend.gui.backend.bridge import BlockingResult, ThreadsafeAsyncDispatcher
from embedagent.frontend.gui.backend.session_events import build_session_event
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
    pending_input = _to_mapping(_read_value(snapshot, "pending_input", None, aliases=("pending_user_input",)))
    pending_interaction = _to_mapping(_read_value(snapshot, "pending_interaction"))
    runtime_environment = _to_mapping(_read_value(snapshot, "runtime_environment"))
    has_pending_input = bool(_read_value(snapshot, "has_pending_input", False, aliases=("has_pending_user_input",)))
    pending_interaction_valid = _read_value(snapshot, "pending_interaction_valid", None)
    if pending_interaction_valid is None:
        pending_interaction_valid = bool(pending_interaction or pending_permission or pending_input)
    return {
        "session_id": str(_read_value(snapshot, "session_id", "") or ""),
        "status": _read_status_value(snapshot),
        "current_mode": str(_read_value(snapshot, "current_mode", "code") or "code"),
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
        "timeline_replay_status": str(_read_value(snapshot, "timeline_replay_status", "replay") or "replay"),
        "timeline_first_seq": int(_read_value(snapshot, "timeline_first_seq", 0) or 0),
        "timeline_last_seq": int(_read_value(snapshot, "timeline_last_seq", 0) or 0),
        "timeline_integrity": str(_read_value(snapshot, "timeline_integrity", "healthy") or "healthy"),
        "pending_interaction_valid": bool(pending_interaction_valid),
        "restore_stop_reason": str(_read_value(snapshot, "restore_stop_reason", "") or ""),
        "restore_consumed_event_count": int(_read_value(snapshot, "restore_consumed_event_count", 0) or 0),
        "restore_transcript_event_count": int(_read_value(snapshot, "restore_transcript_event_count", 0) or 0),
    }


def _serialize_replay_payload(session_id: str, payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        events = payload.get("events")
        return {
            "session_id": str(payload.get("session_id") or session_id),
            "status": str(payload.get("status") or "replay"),
            "first_seq": int(payload.get("first_seq") or 0),
            "last_seq": int(payload.get("last_seq") or 0),
            "reason": str(payload.get("reason") or ""),
            "events": list(events or []) if isinstance(events, list) else [],
        }
    events = list(payload or []) if isinstance(payload, list) else []
    first_seq = int(events[0].get("seq") or 0) if events else 0
    last_seq = int(events[-1].get("seq") or 0) if events else 0
    return {
        "session_id": str(session_id or ""),
        "status": "replay",
        "first_seq": first_seq,
        "last_seq": last_seq,
        "reason": "",
        "events": events,
    }


def _serialize_interaction_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    response = dict(payload or {})
    snapshot = response.get("snapshot")
    if snapshot is not None:
        response["snapshot"] = _serialize_session_snapshot(snapshot)
    return response


def _translate_value_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip()
    if "session_id 不存在" in detail or detail == "session_not_found":
        return HTTPException(status_code=404, detail="session_not_found")
    if detail in ("interaction_gone", "interaction_expired", "未找到待处理的交互请求。"):
        return HTTPException(status_code=410, detail="interaction_expired")
    if detail == "interaction_conflict":
        return HTTPException(status_code=409, detail=detail)
    return HTTPException(status_code=422, detail=detail or "invalid_request")


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
            except Exception:
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
        self._dispatch_message({
            "type": "message",
            "data": {
                "id": message.id,
                "type": message.type.name,
                "content": message.content,
                "timestamp": message.timestamp.isoformat(),
                "metadata": message.metadata
            }
        })
    
    def on_tool_start(self, call: ToolCall) -> None:
        arguments = {}
        if isinstance(call.arguments, dict):
            for key, value in call.arguments.items():
                if str(key).startswith("_"):
                    continue
                arguments[key] = value
        self._dispatch_message({
            "type": "tool_start",
            "data": {
                "tool_name": call.tool_name,
                "arguments": arguments,
                "call_id": call.call_id,
                "turn_id": call.turn_id,
                "step_id": call.step_id,
                "step_index": call.step_index,
                "tool_label": call.arguments.get("_tool_label") if isinstance(call.arguments, dict) else "",
                "permission_category": call.arguments.get("_permission_category") if isinstance(call.arguments, dict) else "",
                "supports_diff_preview": bool(call.arguments.get("_supports_diff_preview")) if isinstance(call.arguments, dict) else False,
                "progress_renderer_key": call.arguments.get("_progress_renderer_key") if isinstance(call.arguments, dict) else "",
                "result_renderer_key": call.arguments.get("_result_renderer_key") if isinstance(call.arguments, dict) else "",
                "runtime_source": call.runtime_source,
                "resolved_tool_roots": call.resolved_tool_roots,
            }
        })
    
    def on_tool_progress(self, call_id: str, progress: Dict[str, Any]) -> None:
        self._dispatch_message({
            "type": "tool_progress",
            "data": {"call_id": call_id, **progress}
        })
    
    def on_tool_finish(self, result: ToolResult) -> None:
        self._dispatch_message({
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
                "tool_label": result.data.get("tool_label") if isinstance(result.data, dict) else "",
                "permission_category": result.data.get("permission_category") if isinstance(result.data, dict) else "",
                "supports_diff_preview": bool(result.data.get("supports_diff_preview")) if isinstance(result.data, dict) else False,
                "progress_renderer_key": result.data.get("progress_renderer_key") if isinstance(result.data, dict) else "",
                "result_renderer_key": result.data.get("result_renderer_key") if isinstance(result.data, dict) else "",
                "runtime_source": result.runtime_source or (result.data.get("runtime_source") if isinstance(result.data, dict) else ""),
                "resolved_tool_roots": result.resolved_tool_roots or (result.data.get("resolved_tool_roots") if isinstance(result.data, dict) else {}),
            }
        })
    
    def on_permission_request(self, request: PermissionRequest) -> bool:
        """同步阻塞等待用户响应"""
        waiter = BlockingResult(False)
        with self._pending_lock:
            self._pending_permissions[request.permission_id] = waiter
        queued = self._dispatch_message({
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
            }
        })
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
        queued = self._dispatch_message({
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
            }
        })
        try:
            if not queued:
                return None
            return waiter.wait(300.0)
        finally:
            with self._pending_lock:
                self._pending_inputs.pop(request.request_id, None)
    
    def on_session_status_change(self, snapshot: SessionSnapshot) -> None:
        snapshot_payload = _serialize_session_snapshot(snapshot)
        self._dispatch_message({
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
                "timeline_replay_status": snapshot_payload["timeline_replay_status"],
                "timeline_integrity": snapshot_payload["timeline_integrity"],
                "pending_interaction_valid": snapshot_payload["pending_interaction_valid"],
            }
        })
    
    def on_stream_delta(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self._dispatch_message({
            "type": "stream_delta",
            "data": {"text": text, **(metadata or {})}
        })

    def on_reasoning_delta(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self._dispatch_message({
            "type": "reasoning_delta",
            "data": {"text": text, **(metadata or {})}
        })

    def on_thinking_state_change(self, active: bool, reason: str = "") -> None:
        self._dispatch_message({
            "type": "thinking_state",
            "data": {"active": active, "reason": reason}
        })

    def on_command_result(self, result: CommandResult) -> None:
        self._dispatch_message({
            "type": "command_result",
            "data": {
                "command_name": result.command_name,
                "success": result.success,
                "message": result.message,
                "data": result.data,
                "turn_id": result.turn_id,
                "step_id": result.step_id,
                "step_index": result.step_index,
            }
        })

    def on_plan_updated(self, plan: PlanSnapshot) -> None:
        self._dispatch_message({
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
            }
        })

    def on_todos_refresh(self) -> None:
        self._dispatch_message({"type": "todos_refresh"})

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
    
    def __init__(self, core: CoreInterface, static_dir: str):
        self.core = core
        self.static_dir = static_dir
        self.frontend = WebSocketFrontend()
        self.app = self._create_app()
        self._current_session_id: Optional[str] = None
        
        # 注册前端回调
        self.core.register_frontend(self.frontend)

    def _call_core(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as exc:
            raise _translate_value_error(exc)

    def _wait_for_interaction_resolution(self, session_id: str, interaction_id: str, timeout_seconds: float = 2.0):
        deadline = time.time() + max(timeout_seconds, 0.0)
        latest = None
        while time.time() < deadline:
            latest = self._call_core(self.core.get_session_snapshot, session_id)
            pending = _to_mapping(_read_value(latest, "pending_interaction"))
            pending_id = str((pending or {}).get("interaction_id") or "").strip()
            if not pending_id or pending_id != str(interaction_id or "").strip():
                return latest
            time.sleep(0.02)
        return latest if latest is not None else self._call_core(self.core.get_session_snapshot, session_id)
    
    def _create_app(self) -> FastAPI:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            _LOGGER.info("GUI Backend starting...")
            yield
            _LOGGER.info("GUI Backend shutting down...")
            self.core.shutdown()
        
        app = FastAPI(title="EmbedAgent GUI", lifespan=lifespan)
        
        # 静态文件
        app.mount("/static", StaticFiles(directory=self.static_dir), name="static")
        
        # 根路由
        @app.get("/")
        async def root():
            return FileResponse(f"{self.static_dir}/index.html")
        
        # API 路由
        @app.get("/api/sessions")
        async def list_sessions(limit: int = 10):
            return {"sessions": self.core.list_sessions(limit)}

        @app.get("/api/sessions/{session_id}")
        async def get_session_snapshot(session_id: str):
            snapshot = self._call_core(self.core.get_session_snapshot, session_id)
            return _serialize_session_snapshot(snapshot)

        @app.post("/api/sessions")
        async def create_session(mode: str = "code"):
            snapshot = self._call_core(self.core.create_session, mode)
            self._current_session_id = str(_read_value(snapshot, "session_id", "") or "")
            return _serialize_session_snapshot(snapshot)

        @app.post("/api/sessions/{session_id}/resume")
        async def resume_session(session_id: str, mode: str = "code"):
            snapshot = self._call_core(self.core.resume_session, session_id, mode)
            self._current_session_id = str(_read_value(snapshot, "session_id", "") or "")
            return _serialize_session_snapshot(snapshot)

        @app.post("/api/sessions/{session_id}/message")
        async def send_message(session_id: str, request: Dict[str, Any]):
            text = request.get("text", "")
            self._current_session_id = session_id
            self._call_core(self.core.submit_message, session_id, text)
            return {"status": "submitted"}

        @app.post("/api/sessions/{session_id}/cancel")
        async def cancel_session(session_id: str):
            self._call_core(self.core.cancel_session, session_id)
            return {"status": "cancelled"}

        @app.post("/api/sessions/{session_id}/mode")
        async def set_mode(session_id: str, request: Dict[str, Any]):
            mode = request.get("mode", "code")
            self._call_core(self.core.set_mode, session_id, mode)
            return {"status": "ok"}

        @app.post("/api/sessions/{session_id}/interactions/{interaction_id}/respond")
        async def respond_to_interaction(session_id: str, interaction_id: str, request: Dict[str, Any]):
            self._current_session_id = session_id
            if self.frontend.resolve_interaction_response(interaction_id, request):
                if bool(request.get("decision")) and bool(request.get("remember")):
                    category = str(request.get("category") or "").strip()
                    if category:
                        remember_method = getattr(self.core, "remember_permission_category", None)
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
            response = self._call_core(self.core.respond_to_interaction, session_id, interaction_id, request)
            if bool(request.get("decision")) and bool(request.get("remember")):
                category = str(request.get("category") or "").strip()
                if category:
                    remember_method = getattr(self.core, "remember_permission_category", None)
                    if callable(remember_method):
                        self._call_core(remember_method, session_id, category)
            return _serialize_interaction_response(response)
        
        @app.get("/api/workspace")
        async def get_workspace():
            return self.core.get_workspace_snapshot()

        @app.get("/api/workspace/recipes")
        async def get_workspace_recipes():
            return self.core.list_workspace_recipes()

        @app.get("/api/tool-catalog")
        async def get_tool_catalog():
            return {"items": self.core.get_tool_catalog()}

        @app.get("/api/sessions/{session_id}/plan")
        async def get_session_plan(session_id: str):
            plan = self._call_core(self.core.get_session_plan, session_id)
            if plan is None:
                return {"plan": None}
            return {
                "plan": {
                    "session_id": plan.session_id,
                    "title": plan.title,
                    "content": plan.content,
                    "updated_at": plan.updated_at,
                    "workflow_state": plan.workflow_state,
                    "path": plan.path,
                    "summary": plan.summary,
                }
            }

        @app.get("/api/sessions/{session_id}/permissions")
        async def get_permission_context(session_id: str):
            context = self._call_core(self.core.get_permission_context, session_id)
            return {
                "session_id": context.session_id,
                "rules_path": context.rules_path,
                "categories": context.categories,
                "rules": context.rules,
                "remembered_categories": context.remembered_categories,
                "auto_approve_all": context.auto_approve_all,
                "auto_approve_writes": context.auto_approve_writes,
                "auto_approve_commands": context.auto_approve_commands,
            }

        @app.get("/api/sessions/{session_id}/timeline")
        async def get_session_timeline(session_id: str, limit: int = 200):
            return self._call_core(self.core.build_structured_timeline, session_id, limit=limit)

        @app.get("/api/sessions/{session_id}/events")
        async def get_session_events(session_id: str, after_seq: int = 0, limit: int = 200):
            payload = self._call_core(self.core.load_session_events_after, session_id, after_seq, limit=limit)
            return _serialize_replay_payload(session_id, payload)
        
        @app.get("/api/files")
        async def list_files(path: str = ".", max_depth: int = 3):
            return {"items": self.core.list_files(path, max_depth)}

        @app.get("/api/files/tree")
        async def list_file_children(path: str = ".", limit: int = 200):
            return {"items": self.core.list_file_children(path, limit)}
        
        @app.get("/api/files/{path:path}")
        async def read_file(path: str):
            try:
                return self.core.read_file(path)
            except Exception as e:
                return {"error": str(e)}
        
        @app.post("/api/files/{path:path}")
        async def write_file(path: str, request: Dict[str, Any]):
            content = request.get("content", "")
            return self.core.write_file(path, content)
        
        @app.post("/api/diff")
        async def get_diff(request: Dict[str, Any]):
            path = request.get("path", "")
            new_content = request.get("new_content", "")
            diff = self.core.get_diff_preview(path, new_content)
            return {
                "path": diff.path,
                "old_content": diff.old_content,
                "new_content": diff.new_content,
                "unified_diff": diff.unified_diff
            }
        
        @app.get("/api/todos")
        async def list_todos(session_id: str = ""):
            return {"todos": self.core.list_todos(session_id=session_id)}

        @app.get("/api/artifacts")
        async def list_artifacts(limit: int = 20):
            return {"items": self.core.list_artifacts(limit=limit)}

        @app.get("/api/artifacts/{reference:path}")
        async def read_artifact(reference: str):
            return self.core.read_artifact(reference)
        
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
            except Exception:
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
            if remember and approved and category and self._current_session_id:
                remember_method = getattr(self.core, "remember_permission_category", None)
                if callable(remember_method):
                    remember_method(self._current_session_id, category)
            self.frontend.handle_permission_response(perm_id, approved)
        
        elif msg_type == "user_input_response":
            req_id = data.get("request_id", "")
            self.frontend.handle_user_input_response(req_id, data)
