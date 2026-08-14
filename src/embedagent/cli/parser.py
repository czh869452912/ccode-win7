from __future__ import annotations

import argparse
import os
from typing import Any, List, Optional

from embedagent.cli.options import CliLaunchOptions, CliOptions


def _positive_integer(value: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("value must be an integer")
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return number


def _add_launch_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", default=".", help="Workspace directory")
    parser.add_argument("--base-url", default=None, help="Model service root URL")
    parser.add_argument("--api-key", default=None, help="Model service API key")
    parser.add_argument("--model", default=None, help="Model name")
    parser.add_argument("--timeout", type=float, default=None, help="Request timeout in seconds")
    parser.add_argument("--max-turns", type=_positive_integer, default=None)
    parser.add_argument("--agent-application", dest="agent_application_id", default=None)
    parser.add_argument("--approve-all", action="store_true", default=None)
    parser.add_argument("--approve-writes", action="store_true", default=None)
    parser.add_argument("--approve-commands", action="store_true", default=None)
    parser.add_argument("--permission-rules", default=None)
    parser.add_argument("--max-context-tokens", type=_positive_integer, default=None)
    parser.add_argument("--reserve-output-tokens", type=_positive_integer, default=None)
    parser.add_argument("--chars-per-token", type=float, default=None)


def _add_session_selection(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", default="", help="Initial session mode")
    parser.add_argument("--resume", default="", help="Session reference to resume")


def _add_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", choices=("text", "json"), default="text")


def _options_from_namespace(namespace: argparse.Namespace) -> CliOptions:
    values = vars(namespace)
    launch = CliLaunchOptions(
        workspace=os.path.realpath(str(values.get("workspace") or ".")),
        base_url=values.get("base_url"),
        api_key=values.get("api_key"),
        model=values.get("model"),
        timeout=values.get("timeout"),
        max_turns=values.get("max_turns"),
        approve_all=values.get("approve_all"),
        approve_writes=values.get("approve_writes"),
        approve_commands=values.get("approve_commands"),
        permission_rules=values.get("permission_rules"),
        agent_application_id=values.get("agent_application_id"),
        max_context_tokens=values.get("max_context_tokens"),
        reserve_output_tokens=values.get("reserve_output_tokens"),
        chars_per_token=values.get("chars_per_token"),
    )
    return CliOptions(
        command=str(values.get("command") or ""),
        launch=launch,
        mode=str(values.get("mode") or ""),
        resume=str(values.get("resume") or ""),
        output=str(values.get("output") or "text"),
        task=str(values.get("task") or ""),
        sessions_action=str(values.get("sessions_action") or ""),
        reference=str(values.get("reference") or ""),
        title=str(values.get("title") or ""),
        limit=int(values.get("limit") or 10),
    )


class CliArgumentParser(argparse.ArgumentParser):
    def parse_args(
        self,
        args: Optional[List[str]] = None,
        namespace: Optional[argparse.Namespace] = None,
    ) -> CliOptions:
        parsed = super().parse_args(args=args, namespace=namespace)
        return _options_from_namespace(parsed)


def _add_session_management_parser(
    subparsers: Any,
    name: str,
    help_text: str,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help=help_text)
    _add_launch_options(parser)
    _add_output(parser)
    return parser


def build_parser() -> CliArgumentParser:
    parser = CliArgumentParser(prog="embedagent", description="EmbedAgent command line host")
    commands = parser.add_subparsers(dest="command", required=True)

    chat = commands.add_parser("chat", help="Start an interactive session")
    _add_launch_options(chat)
    _add_session_selection(chat)

    run = commands.add_parser("run", help="Run one task")
    _add_launch_options(run)
    _add_session_selection(run)
    _add_output(run)
    run.add_argument("task", help="Task to run")

    sessions = commands.add_parser("sessions", help="Manage durable sessions")
    session_commands = sessions.add_subparsers(dest="sessions_action", required=True)

    listed = _add_session_management_parser(session_commands, "list", "List sessions")
    listed.add_argument("--limit", type=_positive_integer, default=10)

    shown = _add_session_management_parser(session_commands, "show", "Show a session")
    shown.add_argument("reference")

    renamed = _add_session_management_parser(session_commands, "rename", "Rename a session")
    renamed.add_argument("reference")
    renamed.add_argument("title")

    archived = _add_session_management_parser(session_commands, "archive", "Archive a session")
    archived.add_argument("reference")

    forked = _add_session_management_parser(session_commands, "fork", "Fork a session")
    forked.add_argument("reference")
    forked.add_argument("--title", default="")
    return parser
