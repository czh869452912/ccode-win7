"""
TUI Frontend Adapter
将现有 TUI 适配到新的 protocol 接口
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from embedagent_protocol import (
    CommandResult,
    FrontendCallbacks,
    Message,
    MessageType,
    PlanSnapshot,
    SessionSnapshot,
    ToolCall,
    ToolResult,
)

if TYPE_CHECKING:
    from embedagent.frontend.tui.app import TerminalApp


class TUIFrontend(FrontendCallbacks):
    """
    TUI 前端适配器
    将 Protocol 回调转换为 TUI 更新
    """

    def __init__(self, app: "TerminalApp", assembler=None):
        del assembler
        self.app = app

    def refresh_timeline(self):
        """Refresh the timeline view with current data."""
        self.app.refresh_views()

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
        reducer.append_line(self.app.state, f"[tool] {call.tool_name} {arguments}")
        self.app.refresh_views()

    def on_tool_progress(self, call_id: str, progress: Dict[str, Any]) -> None:
        """工具进度更新"""
        # TUI 暂不支持进度更新，可以后续添加 spinner
        pass

    def on_tool_finish(self, result: ToolResult) -> None:
        """工具执行完成"""
        from embedagent.frontend.tui import reducer
        from embedagent.frontend.tui.views.timeline import format_observation_line

        payload = {
            "tool_name": result.tool_name,
            "success": result.success,
            "data": result.data,
            "error": result.error,
        }
        reducer.append_line(self.app.state, format_observation_line(payload))
        self.app.refresh_views()

    def on_session_status_change(self, snapshot: SessionSnapshot) -> None:
        """会话状态变化"""
        from embedagent.frontend.tui import reducer

        # 更新状态
        pending_interaction = (
            snapshot.pending_interaction if snapshot.pending_interaction_valid else None
        )
        reducer.set_pending_interaction(self.app.state, pending_interaction)
        reducer.update_snapshot(
            self.app.state,
            status=snapshot.status.value,
            current_mode=snapshot.current_mode,
            pending_interaction=pending_interaction,
            pending_interaction_valid=bool(pending_interaction),
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

        reducer.append_line(
            self.app.state, "[command:/%s] %s" % (result.command_name, result.message)
        )
        self.app.refresh_views()

    def on_plan_updated(self, plan: PlanSnapshot) -> None:
        from embedagent.frontend.tui import reducer

        reducer.append_line(self.app.state, "[plan] %s" % (plan.title or "Current Plan"))
        self.app.refresh_views()
