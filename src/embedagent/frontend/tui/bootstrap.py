from __future__ import annotations

import os

from embedagent.modes import DEFAULT_MODE


class TUIUnavailableError(RuntimeError):
    pass


def load_tui_dependencies():
    try:
        from prompt_toolkit.input.defaults import create_pipe_input
        from prompt_toolkit.output import DummyOutput
        from prompt_toolkit.output.win32 import NoConsoleScreenBufferError
        from rich.console import Console
    except ImportError as exc:
        raise TUIUnavailableError(
            "TUI 依赖未安装。请先安装 `prompt_toolkit` 与 `rich` 后再运行 `--tui`。"
        ) from exc
    return {
        "create_pipe_input": create_pipe_input,
        "DummyOutput": DummyOutput,
        "NoConsoleScreenBufferError": NoConsoleScreenBufferError,
        "Console": Console,
    }


def run_tui(
    session_host,
    workspace: str,
    mode: str,
    resume: str,
    initial_message: str = "",
) -> int:
    deps = load_tui_dependencies()
    from embedagent.frontend.tui.app import TerminalApp

    try:
        app = TerminalApp(
            adapter=session_host.adapter,
            workspace=os.path.realpath(workspace),
            initial_mode=mode or DEFAULT_MODE,
            resume_reference=resume,
            initial_message=initial_message,
            headless=os.environ.get("EMBEDAGENT_TUI_HEADLESS", "").strip() == "1",
            create_pipe_input=deps["create_pipe_input"],
            dummy_output=deps["DummyOutput"](),
        )
        return app.run()
    except deps["NoConsoleScreenBufferError"] as exc:
        raise TUIUnavailableError(
            "当前终端不支持全屏 TUI。请在 cmd.exe、Windows Terminal 或支持控制台缓冲区的终端中运行。"
        ) from exc
