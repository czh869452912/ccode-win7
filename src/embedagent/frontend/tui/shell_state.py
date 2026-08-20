from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Tuple

from embedagent_protocol import KeybindingDescriptor, ShellDescriptor, SurfaceDescriptor

from embedagent.frontend.runtime.commands import is_command_available


@dataclass(frozen=True)
class ShellCommand:
    id: str
    label: str
    group: str
    dispatch: Dict[str, Any] = field(default_factory=dict)
    slash: str = ""


def _slash_for(command_id: str, dispatch: Dict[str, Any]) -> str:
    kind = str(dispatch.get("kind") or "")
    if kind == "interaction.respond":
        return ""
    if kind == "session.command":
        name = str(dispatch.get("command") or "").strip()
    else:
        name = str(command_id or "").rsplit(".", 1)[-1].strip()
    return "/" + name if name else ""


@dataclass
class CommandPaletteState:
    open: bool = False
    query: str = ""
    selected_index: int = 0


@dataclass
class ShellState:
    descriptor: ShellDescriptor = field(default_factory=ShellDescriptor)
    command_palette: CommandPaletteState = field(default_factory=CommandPaletteState)
    commands: Tuple[ShellCommand, ...] = field(init=False, default_factory=tuple)
    surfaces: Tuple[SurfaceDescriptor, ...] = field(init=False, default_factory=tuple)
    keybindings: Tuple[KeybindingDescriptor, ...] = field(init=False, default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.descriptor, ShellDescriptor):
            raise TypeError("descriptor must be a ShellDescriptor")
        self.commands = tuple(
            ShellCommand(
                id=item.id,
                label=item.label,
                group=item.group,
                dispatch=dict(item.dispatch),
                slash=_slash_for(item.id, item.dispatch),
            )
            for item in self.descriptor.commands
        )
        self.surfaces = tuple(self.descriptor.surfaces)
        self.keybindings = tuple(self.descriptor.keybindings)

    def command_by_id(self, command_id: str) -> ShellCommand:
        for command in self.commands:
            if command.id == command_id:
                return command
        return ShellCommand("", "", "")


def slash_commands(
    state: ShellState,
    availability: Dict[str, Any] = None,
) -> List[ShellCommand]:
    values = []
    seen = set()
    for command in state.commands:
        descriptor = next(
            (item for item in state.descriptor.commands if item.id == command.id), None
        )
        if descriptor is not None and not is_command_available(descriptor, availability):
            continue
        if not command.slash:
            continue
        name = command.slash.strip().split()[0].lstrip("/")
        if name in seen:
            continue
        seen.add(name)
        values.append(
            ShellCommand(
                command.id,
                command.label,
                command.group,
                dict(command.dispatch),
                slash="/" + name,
            )
        )
    return values


def slash_name_strings(
    state: ShellState,
    availability: Dict[str, Any] = None,
) -> List[str]:
    return [item.slash.lstrip("/") for item in slash_commands(state, availability)]


def visible_palette_commands(
    state: ShellState,
    query: str = "",
    availability: Dict[str, Any] = None,
) -> List[ShellCommand]:
    normalized = (query or "").strip().lower()
    commands = []
    for command in state.commands:
        descriptor = next(
            (item for item in state.descriptor.commands if item.id == command.id), None
        )
        if descriptor is None or is_command_available(descriptor, availability):
            commands.append(command)
    if not normalized:
        return commands
    matches = []
    for command in commands:
        haystack = " ".join([command.id, command.label, command.group, command.slash]).lower()
        if normalized in haystack:
            matches.append(command)
    return matches


def open_palette(state: ShellState) -> ShellState:
    return replace(
        state,
        command_palette=CommandPaletteState(open=True, query="", selected_index=0),
    )


def close_palette(state: ShellState) -> ShellState:
    return replace(state, command_palette=CommandPaletteState())
