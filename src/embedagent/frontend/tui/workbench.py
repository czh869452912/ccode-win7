from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

RIGHT_PANEL_SURFACES = [
    "interaction",
    "tasks",
    "plan",
    "artifacts",
    "run",
    "problems",
    "review",
    "permissions",
    "runtime",
    "preview",
    "log",
]

BOTTOM_DRAWER_SURFACES = ["terminal", "run_output", "logs"]


@dataclass(frozen=True)
class WorkbenchCommand:
    id: str
    label: str
    group: str
    slash: str = ""
    surface: str = ""
    drawer: str = ""


WORKBENCH_COMMANDS = [
    WorkbenchCommand("session.new", "New Session", "session", "/new"),
    WorkbenchCommand("session.refresh", "Refresh Sessions", "session", "/sessions"),
    WorkbenchCommand("session.resume", "Resume Session", "session", "/resume"),
    WorkbenchCommand("message.send", "Send Message", "message"),
    WorkbenchCommand("message.stop", "Stop Running Turn", "message"),
    WorkbenchCommand("mode.explore", "Mode: Explore", "mode", "/mode explore"),
    WorkbenchCommand("mode.spec", "Mode: Spec", "mode", "/mode spec"),
    WorkbenchCommand("mode.build", "Mode: Build", "mode", "/mode build"),
    WorkbenchCommand("mode.debug", "Mode: Debug", "mode", "/mode debug"),
    WorkbenchCommand("mode.verify", "Mode: Verify", "mode", "/mode verify"),
    WorkbenchCommand("surface.interaction", "Open Interaction", "surface", "", "interaction"),
    WorkbenchCommand("surface.tasks", "Open Tasks", "surface", "/tasks", "tasks"),
    WorkbenchCommand("surface.plan", "Open Plan", "surface", "/plan", "plan"),
    WorkbenchCommand("surface.artifacts", "Open Artifacts", "surface", "/artifacts", "artifacts"),
    WorkbenchCommand("surface.run", "Open Run", "surface", "", "run"),
    WorkbenchCommand("surface.problems", "Open Problems", "surface", "", "problems"),
    WorkbenchCommand("surface.review", "Open Review", "surface", "/review", "review"),
    WorkbenchCommand(
        "surface.permissions", "Open Permissions", "surface", "/permissions", "permissions"
    ),
    WorkbenchCommand("surface.runtime", "Open Runtime", "surface", "/snapshot", "runtime"),
    WorkbenchCommand("surface.preview", "Open Preview", "surface", "", "preview"),
    WorkbenchCommand("surface.log", "Open Log", "surface", "", "log"),
    WorkbenchCommand("drawer.run_output", "Toggle Run Output", "surface", "", "", "run_output"),
    WorkbenchCommand("workspace.files", "Open Files", "workspace", "/workspace"),
    WorkbenchCommand("workflow.diff", "Review Diff", "workflow", "/diff"),
    WorkbenchCommand("view.toggle_right_panel", "Toggle Right Panel", "view"),
    WorkbenchCommand("view.toggle_bottom_drawer", "Toggle Bottom Drawer", "view"),
    WorkbenchCommand("palette.open", "Open Command Palette", "view", "/palette"),
    WorkbenchCommand("palette.close", "Close Command Palette", "view"),
    WorkbenchCommand("snapshot", "Show Snapshot", "session", "/snapshot"),
    WorkbenchCommand("close", "Close Auxiliary View", "view", "/close"),
    WorkbenchCommand("artifact.open", "Open Artifact", "workspace", "/artifact"),
    WorkbenchCommand("file.open", "Open File Preview", "workspace", "/open"),
    WorkbenchCommand("file.edit", "Edit File", "workspace", "/edit"),
    WorkbenchCommand("file.save", "Save File", "workspace", "/save"),
    WorkbenchCommand("explorer.open", "Open Explorer", "workspace", "/explorer"),
    WorkbenchCommand("inspector.open", "Open Inspector", "surface", "/inspector"),
    WorkbenchCommand("timeline.follow", "Toggle Follow Output", "view", "/follow"),
    WorkbenchCommand("help", "Help", "view", "/help"),
    WorkbenchCommand("quit", "Quit", "view", "/quit"),
]


@dataclass
class CommandPaletteState:
    open: bool = False
    query: str = ""
    selected_index: int = 0


@dataclass
class WorkbenchState:
    right_panel_open: bool = True
    bottom_drawer_open: bool = False
    active_surface: str = "tasks"
    active_drawer: str = "run_output"
    command_palette: CommandPaletteState = field(default_factory=CommandPaletteState)


def command_by_id(command_id: str) -> WorkbenchCommand:
    for command in WORKBENCH_COMMANDS:
        if command.id == command_id:
            return command
    return WorkbenchCommand("", "", "")


def slash_command_names() -> List[WorkbenchCommand]:
    values = []
    seen = set()
    for command in WORKBENCH_COMMANDS:
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
                "/" + name,
                command.surface,
                command.drawer,
            )
        )
    return values


def slash_name_strings() -> List[str]:
    return [item.slash.lstrip("/") for item in slash_command_names()]


def visible_palette_commands(query: str = "") -> List[WorkbenchCommand]:
    normalized = (query or "").strip().lower()
    if not normalized:
        return list(WORKBENCH_COMMANDS)
    matches = []
    for command in WORKBENCH_COMMANDS:
        haystack = " ".join([command.id, command.label, command.group, command.slash]).lower()
        if normalized in haystack:
            matches.append(command)
    return matches


def open_surface(state: WorkbenchState, surface: str) -> WorkbenchState:
    if surface not in RIGHT_PANEL_SURFACES:
        return state
    return WorkbenchState(
        right_panel_open=True,
        bottom_drawer_open=state.bottom_drawer_open,
        active_surface=surface,
        active_drawer=state.active_drawer,
        command_palette=state.command_palette,
    )


def open_drawer(state: WorkbenchState, drawer: str) -> WorkbenchState:
    if drawer not in BOTTOM_DRAWER_SURFACES:
        return state
    return WorkbenchState(
        right_panel_open=state.right_panel_open,
        bottom_drawer_open=True,
        active_surface=state.active_surface,
        active_drawer=drawer,
        command_palette=state.command_palette,
    )


def open_palette(state: WorkbenchState) -> WorkbenchState:
    palette = CommandPaletteState(open=True, query="", selected_index=0)
    return WorkbenchState(
        right_panel_open=state.right_panel_open,
        bottom_drawer_open=state.bottom_drawer_open,
        active_surface=state.active_surface,
        active_drawer=state.active_drawer,
        command_palette=palette,
    )


def close_palette(state: WorkbenchState) -> WorkbenchState:
    palette = CommandPaletteState(open=False, query="", selected_index=0)
    return WorkbenchState(
        right_panel_open=state.right_panel_open,
        bottom_drawer_open=state.bottom_drawer_open,
        active_surface=state.active_surface,
        active_drawer=state.active_drawer,
        command_palette=palette,
    )
