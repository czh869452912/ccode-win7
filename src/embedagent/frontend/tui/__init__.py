"""
TUI Frontend - Terminal User Interface
使用 prompt_toolkit 构建的终端界面
"""
from embedagent.frontend.tui.frontend_adapter import TUIFrontend
from embedagent.frontend.tui.bootstrap import run_tui, TUIUnavailableError

__all__ = [
    "TUIFrontend",
    "run_tui",
    "TUIUnavailableError",
    "TerminalApp",
    "launch_tui",
]

# 延迟导入（需要 prompt_toolkit 的模块）
def __getattr__(name):
    if name == "TerminalApp":
        from embedagent.frontend.tui.app import TerminalApp
        return TerminalApp
    elif name == "launch_tui":
        from embedagent.frontend.tui.launcher import launch_tui
        return launch_tui
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
