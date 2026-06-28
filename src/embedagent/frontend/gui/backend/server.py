"""
GUI Backend - FastAPI + WebSocket 服务
为 PyWebView 提供后端 API
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
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
from embedagent.frontend.gui.backend.http_errors import translate_value_error
from embedagent.frontend.gui.backend.preview_service import PreviewService
from embedagent.frontend.gui.backend.protocol_payloads import (
    read_value,
    serialize_session_snapshot,
    to_mapping,
)
from embedagent.frontend.gui.backend.session_events import build_session_event
from embedagent.frontend.gui.backend.source_control_service import SourceControlService
from embedagent.frontend.gui.backend.terminal_service import TerminalService
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
        self._session_event_lock = threading.RLock()
        self._session_event_seq = {}  # type: Dict[str, int]

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

    def _complete_session_event_metadata(
        self, session_id: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        result = dict(metadata or {})
        key = str(session_id or "")
        with self._session_event_lock:
            current = int(self._session_event_seq.get(key, 0) or 0)
            try:
                supplied_seq = int(result.get("seq") or 0)
            except (TypeError, ValueError):
                supplied_seq = 0
            if supplied_seq > 0:
                seq = supplied_seq
                self._session_event_seq[key] = max(current, supplied_seq)
            else:
                seq = current + 1
                self._session_event_seq[key] = seq
        result["seq"] = seq
        if not result.get("event_id"):
            result["event_id"] = "evt-%s" % uuid.uuid4().hex[:12]
        if not result.get("created_at"):
            result["created_at"] = _utc_now()
        return result

    def _session_event_message(
        self, session_id: str, event_name: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        data = dict(payload or {})
        metadata = dict(data.get("_session_event") or {})
        data["_session_event"] = self._complete_session_event_metadata(session_id, metadata)
        return build_session_event(session_id, event_name, data)

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
                    "read_model_invalidations": (
                        list(call.arguments.get("_read_model_invalidations") or [])
                        if isinstance(call.arguments, dict)
                        and isinstance(call.arguments.get("_read_model_invalidations"), list)
                        else []
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
                    "read_model_invalidations": (
                        list(result.data.get("read_model_invalidations") or [])
                        if isinstance(result.data, dict)
                        and isinstance(result.data.get("read_model_invalidations"), list)
                        else []
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
        snapshot_payload = serialize_session_snapshot(snapshot)
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
        self._dispatch_message(self._session_event_message(session_id, event_name, dict(payload)))

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
            raise translate_value_error(exc)

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
            pending = to_mapping(read_value(latest, "pending_interaction"))
            pending_id = str((pending or {}).get("interaction_id") or "").strip()
            if not pending_id or pending_id != str(interaction_id or "").strip():
                return latest
            time.sleep(0.02)
        if latest is not None:
            return latest
        core = self._require_core()
        return self._call_core(core.get_session_snapshot, session_id)

    def _create_app(self) -> FastAPI:
        from embedagent.frontend.gui.backend.routes_app import register_app_routes
        from embedagent.frontend.gui.backend.routes_preview import register_preview_routes
        from embedagent.frontend.gui.backend.routes_sessions import register_session_routes
        from embedagent.frontend.gui.backend.routes_source_control import (
            register_source_control_routes,
        )
        from embedagent.frontend.gui.backend.routes_terminal import register_terminal_routes

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

        register_app_routes(app, self)
        register_session_routes(app, self)
        register_terminal_routes(app, self)
        register_source_control_routes(app, self)
        register_preview_routes(app, self)

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
