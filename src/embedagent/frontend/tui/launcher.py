"""
TUI Launcher
使用现有稳定的 bootstrap 入口启动 TUI。
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional

from embedagent.bundle_policy import load_current_bundle_policy
from embedagent.frontend.tui.bootstrap import TUIUnavailableError, run_tui
from embedagent.hosted import LaunchOverrides, create_hosted_runtime, resolve_launch_config
from embedagent.product_catalog import (
    product_agent_application_registry,
    product_shell_compiler,
)

_LOGGER = logging.getLogger(__name__)


def launch_tui(
    workspace: str,
    mode: str = "build",
    resume: str = "",
    message: str = "",
    headless: bool = False,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
    max_turns: Optional[int] = None,
    approve_all: Optional[bool] = None,
    approve_writes: Optional[bool] = None,
    approve_commands: Optional[bool] = None,
    permission_rules: Optional[str] = None,
    agent_application_id: Optional[str] = None,
):
    """启动 TUI。"""
    bundle_policy = load_current_bundle_policy(__file__)
    bundle_policy.require_shell("tui")
    workspace = os.path.realpath(workspace)
    launch_config = resolve_launch_config(
        workspace,
        overrides=LaunchOverrides(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout=timeout,
            max_turns=max_turns,
            approve_all=approve_all,
            approve_writes=approve_writes,
            approve_commands=approve_commands,
            permission_rules=permission_rules,
            agent_application_id=agent_application_id,
        ),
    )
    runtime = create_hosted_runtime(launch_config)
    allowed_ids = bundle_policy.allowed_agent_application_ids if bundle_policy.bundled else None
    application_record = product_agent_application_registry(allowed_ids).record_by_id(
        launch_config.agent_application_id
    )
    shell_descriptor = product_shell_compiler()(
        application_record.application_id,
        runtime.session_host.get_session_capabilities(""),
    )

    previous_headless = os.environ.get("EMBEDAGENT_TUI_HEADLESS")
    if headless:
        os.environ["EMBEDAGENT_TUI_HEADLESS"] = "1"
    else:
        os.environ.pop("EMBEDAGENT_TUI_HEADLESS", None)
    try:
        return run_tui(
            session_host=runtime.session_host,
            workspace=launch_config.workspace,
            mode=mode,
            resume=resume,
            initial_message=message,
            shell_descriptor=shell_descriptor,
        )
    finally:
        if previous_headless is None:
            os.environ.pop("EMBEDAGENT_TUI_HEADLESS", None)
        else:
            os.environ["EMBEDAGENT_TUI_HEADLESS"] = previous_headless


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EmbedAgent TUI")
    parser.add_argument("workspace", nargs="?", help="Workspace directory")
    parser.add_argument(
        "--workspace", dest="workspace_option", default="", help="Workspace directory"
    )
    parser.add_argument("--mode", default="build", help="Initial mode")
    parser.add_argument("--resume", default="", help="Resume session reference")
    parser.add_argument("--message", "-m", default="", help="Initial message")
    parser.add_argument("--base-url", default="", help="Model service root URL")
    parser.add_argument("--api-key", default="", help="Model service API key")
    parser.add_argument("--model", default="", help="Model name")
    parser.add_argument(
        "--timeout", type=float, default=None, help="Model request timeout in seconds"
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=None,
        help="Optional model/tool loop safety limit; omit for open continuation",
    )
    parser.add_argument(
        "--approve-all",
        action="store_true",
        default=None,
        help="Auto-approve all risky actions",
    )
    parser.add_argument(
        "--approve-writes",
        action="store_true",
        default=None,
        help="Auto-approve file writes",
    )
    parser.add_argument(
        "--approve-commands",
        action="store_true",
        default=None,
        help="Auto-approve commands and toolchain runs",
    )
    parser.add_argument("--permission-rules", default="", help="Permission rules file path")
    parser.add_argument(
        "--agent-application",
        default="",
        help="Agent application id for this hosted runtime",
    )
    parser.add_argument("--headless", action="store_true", help="Headless mode")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    return parser


def main(argv: Optional[list] = None) -> int:
    """命令行入口"""
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
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
            agent_application_id=args.agent_application or None,
        )
    except (TUIUnavailableError, ValueError) as exc:
        _LOGGER.error(str(exc))
        return 1
    return int(exit_code or 0)


if __name__ == "__main__":
    sys.exit(main())
