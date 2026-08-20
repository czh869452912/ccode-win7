from __future__ import annotations

import os

from embedagent_protocol import ShellDescriptor

from embedagent.frontend.runtime import SessionClientRuntime
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
            "TUI 依赖未安装。请安装 `prompt_toolkit` 与 `rich` 后运行 `embedagent-tui`。"
        ) from exc
    return {
        "create_pipe_input": create_pipe_input,
        "DummyOutput": DummyOutput,
        "NoConsoleScreenBufferError": NoConsoleScreenBufferError,
        "Console": Console,
    }


def run_tui(
    runtime: SessionClientRuntime,
    workspace_port,
    workspace: str,
    mode: str,
    resume: str,
    shell_descriptor: ShellDescriptor,
    initial_message: str = "",
) -> int:
    if not isinstance(runtime, SessionClientRuntime):
        raise TypeError("runtime must be a SessionClientRuntime")
    if not isinstance(shell_descriptor, ShellDescriptor):
        raise TypeError("shell_descriptor must be a ShellDescriptor")
    deps = load_tui_dependencies()
    from embedagent.frontend.tui.app import TerminalApp

    try:
        app = TerminalApp(
            runtime=runtime,
            workspace_port=workspace_port,
            shell_descriptor=shell_descriptor,
            workspace=os.path.realpath(workspace),
            initial_mode=mode or DEFAULT_MODE,
            resume_reference=resume,
            initial_message=initial_message,
            headless=os.environ.get("EMBEDAGENT_TUI_HEADLESS", "").strip() == "1",
            create_pipe_input=deps["create_pipe_input"],
            dummy_output=deps["DummyOutput"](),
        )
        runtime.bind_dispatch(app.controller.on_runtime_action)
        return app.run()
    except deps["NoConsoleScreenBufferError"] as exc:
        raise TUIUnavailableError(
            "当前终端不支持全屏 TUI。请在 cmd.exe、Windows Terminal 或支持控制台缓冲区的终端中运行。"
        ) from exc
    finally:
        runtime.close()
