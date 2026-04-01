"""
TUI Frontend Adapter
将现有 TUI 适配到新的 protocol 接口
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from embedagent.protocol import (
    CommandResult,
    FrontendCallbacks,
    Message,
    MessageType,
    PermissionRequest,
    PlanSnapshot,
    SessionSnapshot,
    ToolCall,
    ToolResult,
    UserInputRequest,
)

if TYPE_CHECKING:
    from embedagent.frontend.tui.app import TerminalApp


class TUIFrontend(FrontendCallbacks):
    """
    TUI 前端适配器
    将 Protocol 回调转换为 TUI 更新
    """
    
    def __init__(self, app: "TerminalApp"):
        self.app = app
        self._pending_permission_callbacks: Dict[str, Callable[[bool], None]] = {}
        self._pending_input_callbacks: Dict[str, Callable[[Optional[str]], None]] = {}
    
    def on_message(self, message: Message) -> None:
        """新消息到达"""
        from embedagent.frontend.tui import reducer
        
        # 根据消息类型显示
        if message.type == MessageType.USER:
            reducer.append_line(self.app.state, f"user> {message.content}")
        elif message.type == MessageType.ASSISTANT:
            reducer.append_line(self.app.state, f"assistant> {message.content}")
        elif message.type == MessageType.SYSTEM:
            reducer.append_line(self.app.state, f"[system] {message.content}")
        elif message.type == MessageType.ERROR:
            reducer.append_line(self.app.state, f"[error] {message.content}")
        elif message.type == MessageType.CONTEXT_COMPACTED:
            reducer.append_line(self.app.state, f"[context] {message.content}")
        
        self.app.refresh_views()
    
    def on_tool_start(self, call: ToolCall) -> None:
        """工具开始执行"""
        from embedagent.frontend.tui import reducer
        arguments = {}
        if isinstance(call.arguments, dict):
            for key, value in call.arguments.items():
                if str(key).startswith("_"):
                    continue
                arguments[key] = value
        reducer.append_line(
            self.app.state,
            f"[tool] {call.tool_name} {arguments}"
        )
        self.app.refresh_views()
    
    def on_tool_progress(self, call_id: str, progress: Dict[str, Any]) -> None:
        """工具进度更新"""
        # TUI 暂不支持进度更新，可以后续添加 spinner
        pass
    
    def on_tool_finish(self, result: ToolResult) -> None:
        """工具执行完成"""
        from embedagent.frontend.tui.views.timeline import format_observation_line
        from embedagent.frontend.tui import reducer
        
        payload = {
            "tool_name": result.tool_name,
            "success": result.success,
            "data": result.data,
            "error": result.error
        }
        reducer.append_line(self.app.state, format_observation_line(payload))
        self.app.refresh_views()
    
    def on_permission_request(self, request: PermissionRequest) -> bool:
        """请求用户权限 - TUI 使用阻塞式确认"""
        from embedagent.frontend.tui import reducer
        
        # 设置待确认状态
        reducer.set_pending_permission(self.app.state, request.__dict__)
        reducer.append_line(
            self.app.state,
            f"[permission] {request.reason} (y/n)"
        )
        self.app.refresh_views()
        
        # 等待用户输入（通过 controller 处理）
        # 这里返回 False，实际确认通过 handle_permission_reply 处理
        return False
    
    def on_user_input_request(self, request: UserInputRequest) -> Optional[str]:
        """请求用户输入"""
        from embedagent.frontend.tui import reducer
        
        reducer.set_pending_user_input(self.app.state, request.__dict__)
        reducer.append_line(
            self.app.state,
            f"[question] {request.question}"
        )
        self.app.refresh_views()
        
        # 等待用户输入
        return None
    
    def on_session_status_change(self, snapshot: SessionSnapshot) -> None:
        """会话状态变化"""
        from embedagent.frontend.tui import reducer
        
        # 更新状态
        reducer.update_snapshot(
            self.app.state,
            status=snapshot.status.value,
            current_mode=snapshot.current_mode,
            has_pending_permission=snapshot.has_pending_permission,
            has_pending_user_input=snapshot.has_pending_input
        )
        
        # 如果有错误，显示
        if snapshot.last_error:
            reducer.set_last_error(self.app.state, snapshot.last_error)
            reducer.append_line(self.app.state, f"[error] {snapshot.last_error}")
        
        self.app.refresh_views()
    
    def on_stream_delta(self, text: str, metadata=None) -> None:
        """流式输出增量"""
        from embedagent.frontend.tui import reducer
        reducer.append_delta(self.app.state, text)
        self.app.refresh_views()

    def on_reasoning_delta(self, text: str, metadata=None) -> None:
        from embedagent.frontend.tui import reducer
        reducer.append_line(self.app.state, "[thinking] %s" % text)
        self.app.refresh_views()

    def on_thinking_state_change(self, active: bool, reason: str = "") -> None:
        from embedagent.frontend.tui import reducer
        if active:
            reducer.append_line(self.app.state, "[thinking] 模型正在思考...")
        self.app.refresh_views()

    def on_command_result(self, result: CommandResult) -> None:
        from embedagent.frontend.tui import reducer
        reducer.append_line(self.app.state, "[command:/%s] %s" % (result.command_name, result.message))
        self.app.refresh_views()

    def on_plan_updated(self, plan: PlanSnapshot) -> None:
        from embedagent.frontend.tui import reducer
        reducer.append_line(self.app.state, "[plan] %s" % (plan.title or "Current Plan"))
        self.app.refresh_views()
