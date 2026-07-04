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
    right_panel_surfaces: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    bottom_drawer_surfaces: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    keybindings: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    source_control: Dict[str, Any] = field(default_factory=dict)
    terminal: Dict[str, Any] = field(default_factory=dict)
    thread_lifecycle_actions: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)

    def capabilities(self) -> Dict[str, Any]:
        return {
            "app_commands": _copy_records(self.app_commands),
            "workspace_commands": _copy_records(self.workspace_commands),
            "surfaces": {
                "right_panel": _copy_records(self.right_panel_surfaces),
                "bottom_drawer": _copy_records(self.bottom_drawer_surfaces),
            },
            "keybindings": _copy_records(self.keybindings),
            "source_control": _copy_value(self.source_control),
            "terminal": _copy_value(self.terminal),
            "thread_lifecycle": {
                "actions": _copy_records(self.thread_lifecycle_actions),
            },
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
        right_panel_surfaces=(
            _surface(
                "preview",
                "Preview",
                10,
                icon="B",
                description="Open a local browser preview.",
                command=True,
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
            _thread_lifecycle_action("rename", "Rename", 10),
            _thread_lifecycle_action("fork", "Fork", 20),
            _thread_lifecycle_action("archive", "Archive", 30, danger=True),
        ),
    )
