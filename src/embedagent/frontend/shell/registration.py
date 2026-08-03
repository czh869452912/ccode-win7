from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

from embedagent_protocol import (
    CommandDescriptor,
    InteractionDescriptor,
    KeybindingDescriptor,
    SurfaceDescriptor,
    TimelineItemDescriptor,
    ToolPresentation,
)


@dataclass(frozen=True)
class CommandContribution:
    descriptor: CommandDescriptor
    order: int


@dataclass(frozen=True)
class SurfaceContribution:
    descriptor: SurfaceDescriptor
    order: int


@dataclass(frozen=True)
class ShellContribution:
    commands: Tuple[CommandContribution, ...] = field(default_factory=tuple)
    surfaces: Tuple[SurfaceContribution, ...] = field(default_factory=tuple)
    keybindings: Tuple[KeybindingDescriptor, ...] = field(default_factory=tuple)
    tool_presentations: Tuple[ToolPresentation, ...] = field(default_factory=tuple)
    timeline_items: Tuple[TimelineItemDescriptor, ...] = field(default_factory=tuple)
    interactions: Tuple[InteractionDescriptor, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ShellContributionRegistry:
    generic: ShellContribution = field(default_factory=ShellContribution)
    applications: Dict[str, ShellContribution] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "applications", dict(self.applications or {}))

    def selected(self, application_id: str) -> ShellContribution:
        selected_id = str(application_id or "").strip()
        if not selected_id:
            return ShellContribution()
        try:
            return self.applications[selected_id]
        except KeyError:
            raise ValueError("unknown_shell_application:%s" % selected_id)

    def compile(self, application_id: str, session_capabilities: dict):
        from embedagent.frontend.shell.compiler import compile_shell_descriptor

        return compile_shell_descriptor(
            self,
            application_id=application_id,
            session_capabilities=session_capabilities,
        )
