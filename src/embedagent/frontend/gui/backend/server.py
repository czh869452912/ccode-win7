"""
GUI Backend - FastAPI + WebSocket 服务
为 PyWebView 提供后端 API
"""

from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, Set

from embedagent_host.frontend_errors import FrontendPortError
from embedagent_protocol import SessionEventEnvelope, SessionEventSink
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from embedagent.frontend.gui.backend.app_host import (
    GUIAppHost,
    NoActiveWorkspaceError,
)
from embedagent.frontend.gui.backend.app_shell import AppShellService
from embedagent.frontend.gui.backend.bridge import ThreadsafeAsyncDispatcher
from embedagent.frontend.gui.backend.http_errors import (
    frontend_port_http_error,
    translate_value_error,
)
from embedagent.frontend.gui.backend.preview_service import PreviewService
from embedagent.frontend.gui.backend.source_control_service import SourceControlService
from embedagent.frontend.gui.backend.terminal_service import TerminalService

_LOGGER = logging.getLogger(__name__)


class WebSocketFrontend(SessionEventSink):
    """
    WebSocket 前端适配器
    将 Core 的回调转换为 WebSocket 消息发送给前端
    """

    def __init__(self):
        self.connections: Set[WebSocket] = set()
        self._connections_lock = threading.RLock()
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

    def on_session_event(self, envelope: SessionEventEnvelope) -> None:
        self._dispatch_message({"type": "session_event", "data": envelope.to_dict()})


class GUIBackend:
    """GUI 后端服务"""

    def __init__(
        self,
        static_dir: str = "",
        app_host: Optional[GUIAppHost] = None,
        frontend: Optional[SessionEventSink] = None,
        host_diagnostics: Optional[Dict[str, Any]] = None,
        shell_compiler: Any = None,
        terminal_service: Optional[Any] = None,
        source_control_service: Optional[Any] = None,
        preview_service: Optional[Any] = None,
    ):
        if app_host is None:
            raise ValueError("app_host_required")
        if not callable(shell_compiler):
            raise ValueError("shell_compiler_required")
        self.static_dir = static_dir
        self.frontend = frontend if frontend is not None else WebSocketFrontend()
        self.app_host = app_host
        self.app_shell = AppShellService(
            self.app_host,
            shell_compiler=shell_compiler,
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

    def _call_port(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except NoActiveWorkspaceError:
            raise HTTPException(status_code=409, detail="no_active_workspace")
        except FrontendPortError as exc:
            raise frontend_port_http_error(exc)
        except ValueError as exc:
            raise translate_value_error(exc)

    def _require_session_port(self):
        try:
            return self.app_host.require_session_port()
        except NoActiveWorkspaceError:
            raise HTTPException(status_code=409, detail="no_active_workspace")

    def _require_workspace_port(self):
        try:
            return self.app_host.require_workspace_port()
        except NoActiveWorkspaceError:
            raise HTTPException(status_code=409, detail="no_active_workspace")

    def _terminal(self) -> Any:
        self._require_workspace_port()
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
        self._require_workspace_port()
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
        return None
