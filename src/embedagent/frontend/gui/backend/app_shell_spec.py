from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple


def _copy_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _copy_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy_value(item) for item in value]
    return value


def _copy_records(records: Tuple[Dict[str, Any], ...]) -> list:
    return [_copy_value(record) for record in records]


@dataclass(frozen=True)
class AppShellSpec(object):
    app_commands: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    workspace_commands: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    workbench_commands: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    command_palette_groups: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    command_palette_labels: Dict[str, Any] = field(default_factory=dict)
    surface_chrome: Dict[str, Any] = field(default_factory=dict)
    right_panel_surfaces: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    bottom_drawer_surfaces: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    keybindings: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    source_control: Dict[str, Any] = field(default_factory=dict)
    terminal: Dict[str, Any] = field(default_factory=dict)
    thread_lifecycle_actions: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    home: Dict[str, Any] = field(default_factory=dict)

    def capabilities(self) -> Dict[str, Any]:
        return {
            "app_commands": _copy_records(self.app_commands),
            "workspace_commands": _copy_records(self.workspace_commands),
            "workbench_commands": _copy_records(self.workbench_commands),
            "command_palette": {
                "groups": _copy_records(self.command_palette_groups),
                "labels": _copy_value(self.command_palette_labels),
            },
            "surfaces": {
                "right_panel": _copy_records(self.right_panel_surfaces),
                "bottom_drawer": _copy_records(self.bottom_drawer_surfaces),
                "chrome": _copy_value(self.surface_chrome),
            },
            "keybindings": _copy_records(self.keybindings),
            "source_control": _copy_value(self.source_control),
            "terminal": _copy_value(self.terminal),
            "thread_lifecycle": {
                "actions": _copy_records(self.thread_lifecycle_actions),
            },
            "home": _copy_value(self.home),
        }


def _surface(surface_id: str, title: str, launcher_order: int, **metadata: Any) -> Dict[str, Any]:
    record = {
        "id": surface_id,
        "title": title,
        "launcher_order": launcher_order,
    }
    record.update(metadata)
    return record


def _keybinding(key: str, command_id: str, when: str = "always") -> Dict[str, Any]:
    return {
        "key": key,
        "command_id": command_id,
        "when": when,
    }


def _command(
    command_id: str,
    group: str,
    label: str,
    order: int,
    **metadata: Any,
) -> Dict[str, Any]:
    record = {
        "id": command_id,
        "group": group,
        "label": label,
        "order": order,
        "visible_when": "always",
    }
    record.update(metadata)
    return record


def _palette_group(
    group_id: str,
    title: str,
    description: str,
    order: int,
    **metadata: Any,
) -> Dict[str, Any]:
    record = {
        "id": group_id,
        "title": title,
        "description": description,
        "order": order,
    }
    record.update(metadata)
    return record


def _thread_lifecycle_action(
    action_id: str,
    label: str,
    order: int,
    **metadata: Any,
) -> Dict[str, Any]:
    record = {
        "id": action_id,
        "label": label,
        "capability": action_id,
        "order": order,
    }
    record.update(metadata)
    return record


def default_app_shell_spec() -> AppShellSpec:
    return AppShellSpec(
        app_commands=(
            _command("app.settings", "app", "Open Settings", 10, surface="settings"),
            _command(
                "app.diagnostics",
                "app",
                "Open Diagnostics",
                20,
                surface="diagnostics",
            ),
            _command(
                "app.source_control",
                "app",
                "Open Source Control",
                30,
                surface="source_control",
                keywords=["git", "changes", "source", "source_control"],
            ),
            _command("app.reload", "app", "Reload App Shell", 40),
        ),
        workspace_commands=(
            _command(
                "workspace.open",
                "workspace",
                "Open Workspace",
                10,
                keywords=["project", "folder"],
            ),
            _command(
                "workspace.refresh",
                "workspace",
                "Refresh Workspaces",
                20,
                keywords=["reload", "recent"],
            ),
            _command(
                "workspace.remove_current",
                "workspace",
                "Remove Current Workspace From Recents",
                30,
                visible_when="has_workspace",
                keywords=["forget", "recent"],
            ),
        ),
        workbench_commands=(
            _command("session.new", "session", "New Session", 10, slash="/new"),
            _command(
                "thread.new",
                "session",
                "New Thread",
                20,
                slash="",
                keywords=["session", "chat"],
            ),
            _command(
                "session.refresh",
                "session",
                "Refresh Sessions",
                30,
                slash="/sessions",
            ),
            _command(
                "session.resume",
                "session",
                "Resume Session",
                40,
                slash="/resume",
            ),
            _command(
                "message.send",
                "message",
                "Send Message",
                10,
                visible_when="composer_ready",
            ),
            _command(
                "message.stop",
                "message",
                "Stop Running Turn",
                20,
                visible_when="running",
            ),
            _command(
                "view.toggle_right_panel",
                "view",
                "Toggle Right Panel",
                10,
            ),
            _command(
                "view.toggle_bottom_drawer",
                "view",
                "Toggle Bottom Drawer",
                20,
            ),
            _command(
                "palette.open",
                "view",
                "Open Command Palette",
                30,
            ),
            _command(
                "palette.close",
                "view",
                "Close Command Palette",
                40,
                visible_when="palette_open",
            ),
        ),
        command_palette_groups=(
            _palette_group("app", "App", "App shell commands", 10),
            _palette_group("session", "Sessions", "Create, refresh, and resume threads", 20),
            _palette_group("message", "Message", "Send or stop the current turn", 30),
            _palette_group("mode", "Mode", "Switch the active agent mode", 40),
            _palette_group("surface", "Surface", "Open workbench surfaces", 50),
            _palette_group("workspace", "Workspace", "Open or refresh local workspaces", 60),
            _palette_group("workflow", "Workflow", "Run workflow views", 70),
            _palette_group("view", "View", "Toggle workbench layout", 80),
        ),
        command_palette_labels={
            "root_title": "Command palette",
            "submenu_title": "Command group",
            "search_label": "Command search",
            "root_placeholder": "Search commands, sessions, workspaces",
            "submenu_placeholder": "Search this group",
            "root_empty": "No matching commands, sessions, or workspaces",
            "submenu_empty": "No matching commands in this group",
            "commands_section": "Commands",
            "sessions_section": "Sessions",
            "workspaces_section": "Workspaces",
            "current_label": "Current",
            "missing_label": "Missing",
            "workspace_meta": "Workspace",
            "workspace_fallback": "Workspace",
            "session_fallback_prefix": "Session",
        },
        surface_chrome={
            "right_panel_aria_label": "Right panel",
            "add_surface_label": "Add panel surface",
            "empty_title": "Open a surface",
            "empty_body": "Choose what to show in the right panel.",
            "surface_actions_label_prefix": "Surface actions for",
            "close_label_prefix": "Close",
            "close_action_label": "Close",
            "close_others_action_label": "Close others",
            "close_to_right_action_label": "Close to the right",
            "close_all_action_label": "Close all",
            "default_icon": "S",
        },
        right_panel_surfaces=(
            _surface(
                "preview",
                "Preview",
                10,
                icon="B",
                description="Open a local browser preview.",
                command=True,
                command_label="Open Preview",
                slash="/preview",
                visible_when="always",
                default_resource_id="",
                close_behavior="closable",
                keywords=["browser", "localhost", "web"],
            ),
            _surface(
                "files",
                "Files",
                20,
                icon="F",
                description="Browse workspace files.",
                command=True,
                command_label="Open Files",
                slash="/workspace",
                visible_when="always",
                default_resource_id="",
                close_behavior="closable",
            ),
            _surface(
                "terminal",
                "Terminal",
                30,
                icon="T",
                description="Use a shell in this workspace.",
                command=True,
                command_label="Open Terminal",
                slash="",
                visible_when="has_session",
                default_resource_id="",
                close_behavior="closable",
            ),
            _surface(
                "diff",
                "Diff",
                40,
                icon="D",
                description="Review local changes.",
                command=True,
                command_label="Open Diff",
                slash="/diff",
                visible_when="always",
                default_resource_id="current",
                close_behavior="closable",
                keywords=["git", "changes", "diff"],
            ),
            _surface(
                "plan",
                "Plan",
                50,
                icon="P",
                description="Inspect the current plan.",
                command=True,
                command_label="Open Plan",
                slash="/plan",
                visible_when="always",
                default_resource_id="",
                close_behavior="closable",
            ),
            _surface(
                "source_control",
                "Source Control",
                60,
                icon="S",
                description="Review local Git status.",
                command=True,
                command_label="Open Source Control",
                slash="",
                visible_when="always",
                default_resource_id="",
                close_behavior="closable",
                read_only=True,
                offline=True,
                keywords=["git", "changes", "local"],
            ),
            _surface(
                "settings",
                "Settings",
                70,
                icon="G",
                description="Adjust app-shell preferences.",
                command=True,
                command_label="Open Settings",
                slash="",
                visible_when="always",
                default_resource_id="",
                close_behavior="closable",
            ),
            _surface(
                "diagnostics",
                "Diagnostics",
                80,
                icon="I",
                description="Inspect app-shell health.",
                command=True,
                command_label="Open Diagnostics",
                slash="",
                visible_when="always",
                default_resource_id="",
                close_behavior="closable",
            ),
        ),
        bottom_drawer_surfaces=(
            _surface(
                "run_output",
                "Run Output",
                10,
                icon="R",
                description="Show turn and tool output.",
                command=True,
                command_label="Toggle Run Output",
                visible_when="always",
                close_behavior="pinned",
            ),
            _surface(
                "terminal",
                "Terminal",
                20,
                icon="T",
                description="Use a shell in this workspace.",
                command=True,
                command_label="Open Terminal",
                visible_when="has_session",
                close_behavior="pinned",
            ),
            _surface(
                "logs",
                "Logs",
                30,
                icon="L",
                description="Inspect renderer and runtime logs.",
                command=True,
                command_label="Open Logs",
                visible_when="always",
                close_behavior="pinned",
            ),
        ),
        keybindings=(
            _keybinding("mod+k", "palette.open", "not_palette"),
            _keybinding("escape", "palette.close", "palette"),
            _keybinding("escape", "message.stop", "running"),
            _keybinding("mod+b", "view.toggle_right_panel"),
            _keybinding("mod+,", "app.settings"),
            _keybinding("mod+j", "view.toggle_bottom_drawer"),
            _keybinding("mod+1", "surface.files"),
            _keybinding("mod+2", "surface.terminal"),
            _keybinding("mod+3", "surface.diff"),
            _keybinding("mod+4", "surface.preview"),
            _keybinding("mod+enter", "message.send", "composer"),
        ),
        source_control={
            "enabled": True,
            "vcs": ["git"],
            "read_only": True,
            "remote_providers": False,
            "network": False,
            "checkpoints": False,
            "requires_active_workspace": True,
        },
        terminal={
            "enabled": True,
            "pty": False,
            "resize": False,
            "history_persistent": False,
            "max_buffer_bytes": 131072,
        },
        thread_lifecycle_actions=(
            _thread_lifecycle_action(
                "rename",
                "Rename",
                10,
                prompt_title="Rename thread",
                empty_title="Rename failed",
                empty_body="Thread title cannot be empty.",
                failure_title="Rename failed",
            ),
            _thread_lifecycle_action(
                "fork",
                "Fork",
                20,
                prompt_title="Fork thread title",
                prompt_initial="",
                failure_title="Fork failed",
            ),
            _thread_lifecycle_action(
                "archive",
                "Archive",
                30,
                danger=True,
                confirm_title="Archive this thread?",
                success_title="Thread archived",
                success_body="The thread was archived and hidden from the normal thread list.",
                failure_title="Archive failed",
            ),
        ),
        home={
            "workspace": {
                "section_title": "Project",
                "inactive_label": "No workspace",
                "inactive_path": "Open a local project",
                "path_placeholder": "Workspace path",
                "open_label": "Open",
                "open_aria_label": "Open workspace",
                "recents_label": "Recent projects",
                "missing_path_label": "Missing path",
                "remove_label": "Remove",
            },
            "threads": {
                "section_title": "Threads",
                "new_label": "New",
                "empty_title": "No threads yet",
                "empty_body": "Start one for this project.",
                "active_label": "active",
                "actions_label_prefix": "Thread actions for",
            },
        },
    )
