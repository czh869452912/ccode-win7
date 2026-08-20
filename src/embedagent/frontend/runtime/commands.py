from __future__ import annotations

from typing import Any, Dict, List, Optional

from embedagent_protocol import CommandDescriptor, ShellDescriptor


class ShellCommandError(ValueError):
    pass


class UnknownShellCommand(ShellCommandError):
    pass


class UnavailableShellCommand(ShellCommandError):
    pass


class UnsupportedShellDispatch(ShellCommandError):
    pass


def _command_alias(command: CommandDescriptor) -> str:
    dispatch = dict(command.dispatch)
    if str(dispatch.get("kind") or "") != "session.command":
        return ""
    return str(dispatch.get("command") or "").strip().lower().lstrip("/")


def _is_available(command: CommandDescriptor, context: Dict[str, Any]) -> bool:
    availability = dict(command.availability)
    if availability.get("enabled") is False:
        return False
    conditions = availability.get("visible_when")
    if isinstance(conditions, str):
        conditions = [conditions]
    if conditions is None:
        return True
    if not isinstance(conditions, list):
        return False
    return all(bool(context.get(str(item or ""))) for item in conditions)


def is_command_available(
    command: CommandDescriptor,
    availability: Optional[Dict[str, Any]] = None,
) -> bool:
    if not isinstance(command, CommandDescriptor):
        raise TypeError("command must be a CommandDescriptor")
    return _is_available(command, dict(availability or {}))


def resolve_command(
    shell: ShellDescriptor,
    name: str,
    availability: Optional[Dict[str, Any]] = None,
) -> CommandDescriptor:
    if not isinstance(shell, ShellDescriptor):
        raise TypeError("shell must be a ShellDescriptor")
    normalized = str(name or "").strip().lower().lstrip("/")
    if not normalized:
        raise UnknownShellCommand("unknown_shell_command:")
    matches: List[CommandDescriptor] = []
    for command in shell.commands:
        if command.id.lower() == normalized or _command_alias(command) == normalized:
            matches.append(command)
    if not matches:
        raise UnknownShellCommand("unknown_shell_command:%s" % normalized)
    if len(matches) != 1:
        raise UnknownShellCommand("ambiguous_shell_command:%s" % normalized)
    command = matches[0]
    if not is_command_available(command, availability):
        raise UnavailableShellCommand("unavailable_shell_command:%s" % command.id)
    return command
