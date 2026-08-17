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


@dataclass
class ShellContributionRegistry:
    generic: ShellContribution = field(default_factory=ShellContribution)
    applications: Dict[str, ShellContribution] = field(default_factory=dict)
    registered_sources: Dict[str, ShellContribution] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "applications", dict(self.applications or {}))
        object.__setattr__(self, "registered_sources", dict(self.registered_sources or {}))

    def register(self, contribution: ShellContribution, source_id: str):
        if not isinstance(contribution, ShellContribution):
            descriptors = tuple(getattr(contribution, "commands", ()) or ())
            if any(not isinstance(item, CommandDescriptor) for item in descriptors):
                raise TypeError("shell contribution is invalid")
            contribution = ShellContribution(
                commands=tuple(
                    CommandContribution(descriptor=item, order=1000 + index * 10)
                    for index, item in enumerate(descriptors)
                )
            )
        source = str(source_id or "").strip()
        if not source:
            raise ValueError("shell contribution source id is required")
        if source in self.registered_sources:
            raise ValueError("duplicate_shell_source:%s" % source)
        self.registered_sources[source] = contribution

        def dispose() -> None:
            self.registered_sources.pop(source, None)

        return dispose

    def selected(self, application_id: str, active_sources=()) -> ShellContribution:
        selected_id = str(application_id or "").strip()
        if not selected_id:
            return ShellContribution()
        try:
            selected = self.applications[selected_id]
        except KeyError:
            raise ValueError("unknown_shell_application:%s" % selected_id)
        contributions = [selected]
        for source in tuple(active_sources or ()):
            contribution = self.registered_sources.get(str(source))
            if contribution is not None:
                contributions.append(contribution)
        if len(contributions) == 1:
            return selected
        return ShellContribution(
            commands=tuple(item for record in contributions for item in record.commands),
            surfaces=tuple(item for record in contributions for item in record.surfaces),
            keybindings=tuple(item for record in contributions for item in record.keybindings),
            tool_presentations=tuple(
                item for record in contributions for item in record.tool_presentations
            ),
            timeline_items=tuple(item for record in contributions for item in record.timeline_items),
            interactions=tuple(item for record in contributions for item in record.interactions),
        )

    def compile(self, application_id: str, session_capabilities: dict):
        from embedagent.frontend.shell.compiler import compile_shell_descriptor

        return compile_shell_descriptor(
            self,
            application_id=application_id,
            session_capabilities=session_capabilities,
        )
