"""
GUI Backend - FastAPI + WebSocket 服务
为 PyWebView 提供后端 API
"""
from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from embedagent.frontend.gui.backend.bridge import BlockingResult, ThreadsafeAsyncDispatcher
from embedagent.protocol import (
    CoreInterface,
    FrontendCallbacks,
    Message,
    PermissionRequest,
    SessionSnapshot,
    ToolCall,
    ToolResult,
    UserInputRequest,
)

_LOGGER = logging.getLogger(__name__)


class WebSocketFrontend(FrontendCallbacks):
    """
    WebSocket 前端适配器
    将 Core 的回调转换为 WebSocket 消息发送给前端
    """
    
    def __init__(self):
        self.connections: Set[WebSocket] = set()
        self._pending_permissions = {}  # type: Dict[str, BlockingResult[bool]]
        self._pending_inputs = {}  # type: Dict[str, BlockingResult[Optional[str]]]
        self._pending_lock = threading.RLock()
        self._dispatcher = ThreadsafeAsyncDispatcher()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._dispatcher.bind_running_loop()
        self.connections.add(websocket)
        _LOGGER.info(f"WebSocket connected, total: {len(self.connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.connections.discard(websocket)
        _LOGGER.info(f"WebSocket disconnected, total: {len(self.connections)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """广播消息给所有连接的客户端"""
        disconnected = set()
        for conn in self.connections:
            try:
                await conn.send_json(message)
            except:
                disconnected.add(conn)
        
        # 清理断开的连接
        for conn in disconnected:
            self.connections.discard(conn)

    def _dispatch_message(self, message: Dict[str, Any]) -> bool:
        return self._dispatcher.dispatch(lambda: self.broadcast(message))
    
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
        self._dispatch_message({
            "type": "tool_start",
            "data": {
                "tool_name": call.tool_name,
                "arguments": call.arguments,
                "call_id": call.call_id
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
                "execution_time_ms": result.execution_time_ms
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
                "tool_name": request.tool_name,
                "category": request.category,
                "reason": request.reason,
                "details": request.details
            }
        })
        try:
            if not queued:
                return False
            return bool(waiter.wait(300.0))
        finally:
            with self._pending_lock:
                self._pending_permissions.pop(request.permission_id, None)
    
    def on_user_input_request(self, request: UserInputRequest) -> Optional[str]:
        """同步阻塞等待用户响应"""
        waiter = BlockingResult(None)  # type: BlockingResult[Optional[str]]
        with self._pending_lock:
            self._pending_inputs[request.request_id] = waiter
        queued = self._dispatch_message({
            "type": "user_input_request",
            "data": {
                "request_id": request.request_id,
                "tool_name": request.tool_name,
                "question": request.question,
                "options": request.options
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
        self._dispatch_message({
            "type": "session_status",
            "data": {
                "session_id": snapshot.session_id,
                "status": snapshot.status.value,
                "current_mode": snapshot.current_mode,
                "has_pending_permission": snapshot.has_pending_permission,
                "has_pending_input": snapshot.has_pending_input,
                "last_error": snapshot.last_error
            }
        })
    
    def on_stream_delta(self, text: str) -> None:
        self._dispatch_message({
            "type": "stream_delta",
            "data": {"text": text}
        })
    
    # ============ 处理前端响应 ============
    
    def handle_permission_response(self, permission_id: str, approved: bool):
        """处理权限响应"""
        with self._pending_lock:
            waiter = self._pending_permissions.get(permission_id)
        if waiter is not None:
            waiter.resolve(bool(approved))
    
    def handle_user_input_response(self, request_id: str, answer: str):
        """处理用户输入响应"""
        with self._pending_lock:
            waiter = self._pending_inputs.get(request_id)
        if waiter is not None:
            waiter.resolve(answer)


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
        
        @app.post("/api/sessions")
        async def create_session(mode: str = "code"):
            snapshot = self.core.create_session(mode)
            self._current_session_id = snapshot.session_id
            return snapshot
        
        @app.post("/api/sessions/{session_id}/resume")
        async def resume_session(session_id: str, mode: str = "code"):
            snapshot = self.core.resume_session(session_id, mode)
            self._current_session_id = snapshot.session_id
            return snapshot
        
        @app.post("/api/sessions/{session_id}/message")
        async def send_message(session_id: str, request: Dict[str, Any]):
            text = request.get("text", "")
            self._current_session_id = session_id
            self.core.submit_message(session_id, text)
            return {"status": "submitted"}
        
        @app.post("/api/sessions/{session_id}/cancel")
        async def cancel_session(session_id: str):
            self.core.cancel_session(session_id)
            return {"status": "cancelled"}
        
        @app.post("/api/sessions/{session_id}/mode")
        async def set_mode(session_id: str, request: Dict[str, Any]):
            mode = request.get("mode", "code")
            self.core.set_mode(session_id, mode)
            return {"status": "ok"}
        
        @app.get("/api/workspace")
        async def get_workspace():
            return self.core.get_workspace_snapshot()
        
        @app.get("/api/files")
        async def list_files(path: str = ".", max_depth: int = 3):
            return {"items": self.core.list_files(path, max_depth)}
        
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
        async def list_todos():
            return {"todos": self.core.list_todos()}
        
        # WebSocket 路由
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.frontend.connect(websocket)
            try:
                while True:
                    data = await websocket.receive_json()
                    await self._handle_websocket_message(data)
            except WebSocketDisconnect:
                self.frontend.disconnect(websocket)
        
        return app
    
    async def _handle_websocket_message(self, data: Dict[str, Any]):
        """处理 WebSocket 消息"""
        msg_type = data.get("type")
        
        if msg_type == "permission_response":
            perm_id = data.get("permission_id", "")
            approved = data.get("approved", False)
            self.frontend.handle_permission_response(perm_id, approved)
        
        elif msg_type == "user_input_response":
            req_id = data.get("request_id", "")
            answer = data.get("answer", "")
            self.frontend.handle_user_input_response(req_id, answer)
