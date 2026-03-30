"""
TUI Frontend - Terminal User Interface
使用 prompt_toolkit 构建的终端界面
"""
from embedagent.frontend.tui.frontend_adapter import TUIFrontend

__all__ = [
    "TUIFrontend",
]

# 延迟导入（需要 prompt_toolkit 的模块）
def __getattr__(name):
    if name == "TerminalApp":
        from embedagent.frontend.tui.app import TerminalApp
        return TerminalApp
    elif name == "launch_tui":
        from embedagent.frontend.tui.launcher import launch_tui
        return launch_tui
    elif name == "main":
        from embedagent.frontend.tui.launcher import main
        return main
    elif name == "reducer":
        from embedagent.frontend.tui import reducer
        return reducer
    elif name == "TerminalState":
        from embedagent.frontend.tui.state import TerminalState
        return TerminalState
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

# 向后兼容
TUIUnavailableError = Exception
