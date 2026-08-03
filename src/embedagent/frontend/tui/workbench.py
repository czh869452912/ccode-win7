from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Tuple

from embedagent_protocol import KeybindingDescriptor, ShellDescriptor, SurfaceDescriptor


@dataclass(frozen=True)
class WorkbenchCommand:
    id: str
    label: str
    group: str
    dispatch: Dict[str, Any] = field(default_factory=dict)
    slash: str = ""
    surface: str = ""


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
class WorkbenchState:
    shell_descriptor: ShellDescriptor = field(default_factory=ShellDescriptor)
    right_panel_open: bool = False
    bottom_drawer_open: bool = False
    active_surface: str = ""
    active_drawer: str = ""
    command_palette: CommandPaletteState = field(default_factory=CommandPaletteState)
    commands: Tuple[WorkbenchCommand, ...] = field(init=False, default_factory=tuple)
    surfaces: Tuple[SurfaceDescriptor, ...] = field(init=False, default_factory=tuple)
    keybindings: Tuple[KeybindingDescriptor, ...] = field(init=False, default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.shell_descriptor, ShellDescriptor):
            raise TypeError("shell_descriptor must be a ShellDescriptor")
        self.commands = tuple(
            WorkbenchCommand(
                id=item.id,
                label=item.label,
                group=item.group,
                dispatch=dict(item.dispatch),
                slash=_slash_for(item.id, item.dispatch),
                surface=str(item.dispatch.get("surface_id") or ""),
            )
            for item in self.shell_descriptor.commands
        )
        self.surfaces = tuple(self.shell_descriptor.surfaces)
        self.keybindings = tuple(self.shell_descriptor.keybindings)
        secondary_ids = tuple(item.id for item in self.surfaces if item.placement == "secondary")
        if self.active_surface not in secondary_ids:
            self.active_surface = secondary_ids[0] if secondary_ids else ""
        if not secondary_ids:
            self.right_panel_open = False

    def command_by_id(self, command_id: str) -> WorkbenchCommand:
        for command in self.commands:
            if command.id == command_id:
                return command
        return WorkbenchCommand("", "", "")

    def resolve_command(self, name: str) -> WorkbenchCommand:
        normalized = str(name or "").strip().lower().lstrip("/")
        for command in self.commands:
            if command.slash.lstrip("/").lower() == normalized:
                return command
            if command.id.lower() == normalized:
                return command
        return WorkbenchCommand("", "", "")


def slash_command_names(state: WorkbenchState) -> List[WorkbenchCommand]:
    values = []
    seen = set()
    for command in state.commands:
        if not command.slash:
            continue
        name = command.slash.strip().split()[0].lstrip("/")
        if name in seen:
            continue
        seen.add(name)
        values.append(
            WorkbenchCommand(
                command.id,
                command.label,
                command.group,
                dict(command.dispatch),
                slash="/" + name,
                surface=command.surface,
            )
        )
    return values


def slash_name_strings(state: WorkbenchState) -> List[str]:
    return [item.slash.lstrip("/") for item in slash_command_names(state)]


def visible_palette_commands(state: WorkbenchState, query: str = "") -> List[WorkbenchCommand]:
    normalized = (query or "").strip().lower()
    if not normalized:
        return list(state.commands)
    matches = []
    for command in state.commands:
        haystack = " ".join([command.id, command.label, command.group, command.slash]).lower()
        if normalized in haystack:
            matches.append(command)
    return matches


def open_surface(state: WorkbenchState, surface: str) -> WorkbenchState:
    if surface not in [item.id for item in state.surfaces if item.placement == "secondary"]:
        return state
    return replace(state, right_panel_open=True, active_surface=surface)


def open_drawer(state: WorkbenchState, drawer: str) -> WorkbenchState:
    return state


def open_palette(state: WorkbenchState) -> WorkbenchState:
    palette = CommandPaletteState(open=True, query="", selected_index=0)
    return replace(state, command_palette=palette)


def close_palette(state: WorkbenchState) -> WorkbenchState:
    palette = CommandPaletteState(open=False, query="", selected_index=0)
    return replace(state, command_palette=palette)
