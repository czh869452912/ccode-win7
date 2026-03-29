from __future__ import annotations

import os

from embedagent.config import load_config
from embedagent.context import ContextManager, make_context_config
from embedagent.inprocess_adapter import InProcessAdapter
from embedagent.llm import OpenAICompatibleClient
from embedagent.modes import DEFAULT_MODE
from embedagent.permissions import PermissionPolicy
from embedagent.project_memory import ProjectMemoryStore
from embedagent.tools import ToolRuntime


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
    base_url: str,
    api_key: str,
    model: str,
    workspace: str,
    timeout: float,
    max_turns: int,
    mode: str,
    resume: str,
    approve_all: bool,
    approve_writes: bool,
    approve_commands: bool,
    permission_rules: str,
    initial_message: str = "",
) -> int:
    deps = load_tui_dependencies()
    app_config = load_config(os.path.realpath(workspace))
    client = OpenAICompatibleClient(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout=timeout,
    )
    tools = ToolRuntime(workspace, app_config=app_config)
    context_manager = ContextManager(
        config=make_context_config(app_config),
        project_memory=ProjectMemoryStore(os.path.realpath(workspace)),
    )
    permission_policy = PermissionPolicy(
        auto_approve_all=approve_all,
        auto_approve_writes=approve_writes,
        auto_approve_commands=approve_commands,
        workspace=workspace,
        rules_path=permission_rules,
    )
    adapter = InProcessAdapter(
        client=client,
        tools=tools,
        max_turns=max_turns,
        permission_policy=permission_policy,
        context_manager=context_manager,
    )
    from embedagent.frontends.terminal.app import TerminalApp

    try:
        app = TerminalApp(
            adapter=adapter,
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
