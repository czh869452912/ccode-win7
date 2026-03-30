"""
TUI Launcher
使用现有稳定的 bootstrap 入口启动 TUI。
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any, Optional

from embedagent.config import load_config
from embedagent.frontend.tui.bootstrap import TUIUnavailableError, run_tui

_LOGGER = logging.getLogger(__name__)


def _resolve_runtime_value(override: Any, configured: Any, default: Any) -> Any:
    if override is not None:
        if isinstance(override, str):
            if override.strip():
                return override
        else:
            return override
    if configured is not None:
        return configured
    return default


def launch_tui(
    workspace: str,
    mode: str = "code",
    resume: str = "",
    message: str = "",
    headless: bool = False,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
    max_turns: Optional[int] = None,
    approve_all: bool = False,
    approve_writes: bool = False,
    approve_commands: bool = False,
    permission_rules: str = "",
):
    """启动 TUI。"""
    workspace = os.path.realpath(workspace)
    app_config = load_config(workspace)
    resolved_base_url = str(_resolve_runtime_value(base_url, app_config.base_url, "http://127.0.0.1:8000/v1"))
    resolved_api_key = str(_resolve_runtime_value(api_key, app_config.api_key, ""))
    resolved_model = str(_resolve_runtime_value(model, app_config.model, ""))
    resolved_timeout = float(_resolve_runtime_value(timeout, app_config.timeout, 120.0))
    resolved_max_turns = int(_resolve_runtime_value(max_turns, app_config.max_turns, 8))
    if not resolved_model:
        raise ValueError("必须通过 --model 或配置文件提供模型名称。")

    previous_headless = os.environ.get("EMBEDAGENT_TUI_HEADLESS")
    if headless:
        os.environ["EMBEDAGENT_TUI_HEADLESS"] = "1"
    else:
        os.environ.pop("EMBEDAGENT_TUI_HEADLESS", None)
    try:
        return run_tui(
            base_url=resolved_base_url,
            api_key=resolved_api_key,
            model=resolved_model,
            workspace=workspace,
            timeout=resolved_timeout,
            max_turns=resolved_max_turns,
            mode=mode,
            resume=resume,
            approve_all=approve_all,
            approve_writes=approve_writes,
            approve_commands=approve_commands,
            permission_rules=permission_rules,
            initial_message=message,
        )
    finally:
        if previous_headless is None:
            os.environ.pop("EMBEDAGENT_TUI_HEADLESS", None)
        else:
            os.environ["EMBEDAGENT_TUI_HEADLESS"] = previous_headless


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EmbedAgent TUI")
    parser.add_argument("workspace", nargs="?", help="Workspace directory")
    parser.add_argument("--workspace", dest="workspace_option", default="", help="Workspace directory")
    parser.add_argument("--mode", default="code", help="Initial mode")
    parser.add_argument("--resume", default="", help="Resume session reference")
    parser.add_argument("--message", "-m", default="", help="Initial message")
    parser.add_argument("--base-url", default="", help="Model service root URL")
    parser.add_argument("--api-key", default="", help="Model service API key")
    parser.add_argument("--model", default="", help="Model name")
    parser.add_argument("--timeout", type=float, default=None, help="Model request timeout in seconds")
    parser.add_argument("--max-turns", type=int, default=None, help="Maximum turns per session")
    parser.add_argument("--approve-all", action="store_true", help="Auto-approve all risky actions")
    parser.add_argument("--approve-writes", action="store_true", help="Auto-approve file writes")
    parser.add_argument("--approve-commands", action="store_true", help="Auto-approve commands and toolchain runs")
    parser.add_argument("--permission-rules", default="", help="Permission rules file path")
    parser.add_argument("--headless", action="store_true", help="Headless mode")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    return parser


def main(argv: Optional[list] = None) -> int:
    """命令行入口"""
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    workspace_arg = args.workspace_option or args.workspace or os.getcwd()
    workspace = os.path.abspath(workspace_arg)
    if not os.path.isdir(workspace):
        _LOGGER.error(f"Workspace not found: {workspace}")
        return 1

    try:
        exit_code = launch_tui(
            workspace=workspace,
            mode=args.mode,
            resume=args.resume,
            message=args.message,
            headless=args.headless,
            base_url=args.base_url or None,
            api_key=args.api_key or None,
            model=args.model or None,
            timeout=args.timeout,
            max_turns=args.max_turns,
            approve_all=args.approve_all,
            approve_writes=args.approve_writes,
            approve_commands=args.approve_commands,
            permission_rules=args.permission_rules,
        )
    except (TUIUnavailableError, ValueError) as exc:
        _LOGGER.error(str(exc))
        return 1
    return int(exit_code or 0)


if __name__ == "__main__":
    sys.exit(main())
