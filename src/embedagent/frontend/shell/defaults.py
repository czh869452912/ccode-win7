from __future__ import annotations

from typing import Any, Dict

from embedagent_protocol import (
    CommandDescriptor,
    InteractionDescriptor,
    KeybindingDescriptor,
    SurfaceDescriptor,
    TimelineItemDescriptor,
)

from embedagent.frontend.shell.registration import (
    CommandContribution,
    ShellContribution,
    SurfaceContribution,
)


def _command(
    command_id: str,
    label: str,
    group: str,
    dispatch_kind: str,
    order: int,
    dispatch: Dict[str, Any] = None,
    availability: Dict[str, Any] = None,
) -> CommandContribution:
    dispatch_record = {"kind": dispatch_kind}
    dispatch_record.update(dict(dispatch or {}))
    return CommandContribution(
        descriptor=CommandDescriptor(
            id=command_id,
            label=label,
            group=group,
            dispatch=dispatch_record,
            availability=dict(availability or {}),
        ),
        order=order,
    )


def _surface(
    surface_id: str,
    label: str,
    placement: str,
    renderer_key: str,
    order: int,
) -> SurfaceContribution:
    return SurfaceContribution(
        descriptor=SurfaceDescriptor(
            id=surface_id,
            label=label,
            placement=placement,
            renderer_key=renderer_key,
        ),
        order=order,
    )


def minimal_shell_contribution() -> ShellContribution:
    return ShellContribution(
        commands=(
            _command(
                "session.new",
                "New Session",
                "session",
                "session.create",
                10,
            ),
            _command(
                "session.select",
                "Select Session",
                "session",
                "session.select",
                20,
            ),
            _command(
                "session.rename",
                "Rename Session",
                "session",
                "session.rename",
                30,
            ),
            _command(
                "session.archive",
                "Archive Session",
                "session",
                "session.archive",
                40,
            ),
            _command(
                "session.fork",
                "Fork Session",
                "session",
                "session.fork",
                50,
            ),
            _command(
                "session.cancel",
                "Cancel Turn",
                "session",
                "session.cancel",
                60,
            ),
            _command(
                "session.mode",
                "Select Mode",
                "session",
                "session.mode",
                70,
            ),
            _command(
                "shell.command_palette",
                "Open Commands",
                "shell",
                "shell.surface",
                80,
                {"surface_id": "session.command_palette"},
            ),
            _command(
                "shell.composer.focus",
                "Focus Composer",
                "shell",
                "shell.surface",
                90,
                {"surface_id": "session.composer"},
            ),
            _command(
                "interaction.permission.respond",
                "Respond To Permission",
                "interaction",
                "interaction.respond",
                100,
                {"interaction_kind": "permission"},
            ),
            _command(
                "interaction.input.respond",
                "Respond To Input",
                "interaction",
                "interaction.respond",
                110,
                {"interaction_kind": "user_input"},
            ),
        ),
        surfaces=(
            _surface(
                "session.command_palette",
                "Commands",
                "overlay",
                "command_palette",
                10,
            ),
            _surface(
                "session.interaction",
                "Interaction",
                "overlay",
                "interaction",
                20,
            ),
            _surface(
                "session.composer",
                "Composer",
                "overlay",
                "composer",
                30,
            ),
        ),
        keybindings=(
            KeybindingDescriptor(
                command_id="shell.composer.focus",
                keys="ctrl+l",
            ),
            KeybindingDescriptor(
                command_id="shell.command_palette",
                keys="ctrl+p",
            ),
            KeybindingDescriptor(command_id="session.new", keys="ctrl+n"),
            KeybindingDescriptor(command_id="session.cancel", keys="ctrl+c"),
        ),
        timeline_items=(
            TimelineItemDescriptor(
                event_kind="message",
                renderer_key="generic_timeline",
                priority=10,
            ),
            TimelineItemDescriptor(
                event_kind="reasoning",
                renderer_key="generic_timeline",
                priority=20,
            ),
            TimelineItemDescriptor(
                event_kind="tool",
                renderer_key="tool",
                priority=30,
            ),
            TimelineItemDescriptor(
                event_kind="error",
                renderer_key="generic_timeline",
                priority=40,
            ),
            TimelineItemDescriptor(
                event_kind="workflow_summary",
                renderer_key="workflow_summary",
                priority=50,
            ),
            TimelineItemDescriptor(
                event_kind="file_reference",
                renderer_key="file_reference",
                priority=60,
            ),
            TimelineItemDescriptor(
                event_kind="inline_diff",
                renderer_key="inline_diff",
                priority=70,
            ),
        ),
        interactions=(
            InteractionDescriptor(kind="permission", renderer_key="interaction"),
            InteractionDescriptor(kind="user_input", renderer_key="interaction"),
        ),
    )


def desktop_file_contribution() -> ShellContribution:
    return ShellContribution(
        commands=(
            _command(
                "workspace.open",
                "Open Workspace",
                "workspace",
                "workspace.open",
                200,
            ),
            _command(
                "workspace.files",
                "Open Files",
                "workspace",
                "shell.surface",
                210,
                {"surface_id": "files"},
            ),
        ),
        surfaces=(
            _surface(
                "files",
                "Files",
                "secondary",
                "file_reference",
                200,
            ),
        ),
    )


def terminal_contribution() -> ShellContribution:
    return ShellContribution(
        commands=(
            _command(
                "shell.terminal",
                "Open Terminal",
                "shell",
                "shell.surface",
                300,
                {"surface_id": "terminal"},
            ),
        ),
        surfaces=(
            _surface(
                "terminal",
                "Terminal",
                "secondary",
                "terminal",
                300,
            ),
        ),
    )


def source_control_contribution() -> ShellContribution:
    return ShellContribution(
        commands=(
            _command(
                "shell.source_control",
                "Open Source Control",
                "shell",
                "shell.surface",
                400,
                {"surface_id": "source_control"},
            ),
        ),
        surfaces=(
            _surface(
                "source_control",
                "Source Control",
                "secondary",
                "source_control",
                400,
            ),
        ),
    )


def preview_contribution() -> ShellContribution:
    return ShellContribution(
        commands=(
            _command(
                "shell.preview",
                "Open Preview",
                "shell",
                "shell.surface",
                500,
                {"surface_id": "preview"},
            ),
        ),
        surfaces=(
            _surface(
                "preview",
                "Preview",
                "secondary",
                "preview",
                500,
            ),
        ),
    )


def cpp_workflow_contribution() -> ShellContribution:
    commands = []
    for order, command_id, label, capability_id in (
        (1000, "workflow.run", "Run Recipe", "run"),
        (1010, "workflow.review", "Review", "review"),
        (1020, "workflow.recipes", "List Recipes", "recipes"),
        (1030, "workflow.diff", "View Diff", "diff"),
        (1040, "workflow.tasks", "View Tasks", "tasks"),
    ):
        commands.append(
            _command(
                command_id,
                label,
                "workflow",
                "session.command",
                order,
                {"command": capability_id},
                {"capability_id": capability_id},
            )
        )
    return ShellContribution(commands=tuple(commands))
