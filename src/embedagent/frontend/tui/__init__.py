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
]
