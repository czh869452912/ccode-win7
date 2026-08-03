from __future__ import annotations

import os

from embedagent.modes import DEFAULT_MODE


class TUIUnavailableError(RuntimeError):
    pass


class _RuntimeActionDispatch(object):
    def __init__(self) -> None:
        self._handler = None

    def bind(self, handler) -> None:
        if self._handler is not None:
            raise RuntimeError("terminal_runtime_dispatch_already_bound")
        self._handler = handler

    def __call__(self, action) -> None:
        if self._handler is None:
            raise RuntimeError("terminal_runtime_dispatch_not_bound")
        self._handler(action)


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
    from embedagent.frontend.tui.runtime import TerminalRuntime

    action_dispatch = _RuntimeActionDispatch()
    runtime = TerminalRuntime(session_host, dispatch=action_dispatch)
    try:
        app = TerminalApp(
            runtime=runtime,
            workspace=os.path.realpath(workspace),
            initial_mode=mode or DEFAULT_MODE,
            resume_reference=resume,
            initial_message=initial_message,
            headless=os.environ.get("EMBEDAGENT_TUI_HEADLESS", "").strip() == "1",
            create_pipe_input=deps["create_pipe_input"],
            dummy_output=deps["DummyOutput"](),
        )
        action_dispatch.bind(app.controller.on_runtime_action)
        return app.run()
    except deps["NoConsoleScreenBufferError"] as exc:
        raise TUIUnavailableError(
            "当前终端不支持全屏 TUI。请在 cmd.exe、Windows Terminal 或支持控制台缓冲区的终端中运行。"
        ) from exc
    finally:
        runtime.close()
