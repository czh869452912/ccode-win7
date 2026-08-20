from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set, Tuple

from embedagent_protocol import ShellDescriptor
from embedagent_protocol.versions import FRONTEND_PROTOCOL_SCHEMA_VERSION

from embedagent.frontend.shell.registration import (
    CommandContribution,
    ShellContribution,
    ShellContributionRegistry,
    SurfaceContribution,
)

SUPPORTED_RENDERERS = frozenset(
    (
        "command_palette",
        "composer",
        "interaction",
        "generic_timeline",
        "tool",
        "workflow_summary",
        "file_reference",
        "inline_diff",
        "terminal",
        "source_control",
        "preview",
    )
)
SUPPORTED_DISPATCH_KINDS = frozenset(
    (
        "session.create",
        "session.cancel",
        "session.rename",
        "session.archive",
        "session.fork",
        "session.mode",
        "session.command",
        "session.select",
        "workspace.open",
        "shell.surface",
        "interaction.respond",
    )
)


def _merged_records(
    generic: ShellContribution,
    selected: ShellContribution,
    attribute: str,
) -> Tuple[Any, ...]:
    return tuple(getattr(generic, attribute)) + tuple(getattr(selected, attribute))


def _require_unique_order(kind: str, records: Iterable[Any]) -> None:
    orders: Set[int] = set()
    for record in records:
        if isinstance(record.order, bool) or not isinstance(record.order, int):
            raise ValueError("invalid_%s_order:%s" % (kind, record.order))
        if record.order in orders:
            raise ValueError("duplicate_%s_order:%s" % (kind, record.order))
        orders.add(record.order)


def _require_unique_value(kind: str, values: Iterable[str]) -> None:
    seen: Set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError("duplicate_%s:%s" % (kind, value))
        seen.add(value)


def _active_command_ids(session_capabilities: Dict[str, Any]) -> Set[str]:
    ids: Set[str] = set()
    commands = session_capabilities.get("commands", [])
    if not isinstance(commands, list):
        raise ValueError("session_capabilities.commands must be a list")
    for record in commands:
        if not isinstance(record, dict):
            raise ValueError("session_capabilities.commands contains an invalid item")
        if record.get("active") is False:
            continue
        command_id = str(record.get("id") or record.get("name") or "").strip()
        if command_id:
            ids.add(command_id)
    return ids


def _command_is_available(
    record: CommandContribution,
    active_command_ids: Set[str],
) -> bool:
    availability = record.descriptor.availability
    capability_id = str(availability.get("capability_id") or "").strip()
    if capability_id:
        return capability_id in active_command_ids
    required = availability.get("capability_ids")
    if required is None:
        return True
    if not isinstance(required, list):
        raise ValueError("command_availability_capability_ids:%s" % record.descriptor.id)
    return all(str(item) in active_command_ids for item in required)


def _validate_renderer(renderer_key: str, owner: str) -> None:
    if renderer_key not in SUPPORTED_RENDERERS:
        raise ValueError("unknown_shell_renderer:%s:%s" % (owner, renderer_key))


def _validate_dispatch(record: CommandContribution) -> None:
    kind = str(record.descriptor.dispatch.get("kind") or "")
    if kind not in SUPPORTED_DISPATCH_KINDS:
        raise ValueError("unknown_shell_dispatch:%s:%s" % (record.descriptor.id, kind))


def compile_shell_descriptor(
    registry: ShellContributionRegistry,
    application_id: str,
    session_capabilities: Dict[str, Any],
) -> ShellDescriptor:
    if not isinstance(registry, ShellContributionRegistry):
        raise ValueError("shell_registry is invalid")
    if not isinstance(session_capabilities, dict):
        raise ValueError("session_capabilities must be a mapping")
    active_sources = session_capabilities.get("application_sources", ())
    if not isinstance(active_sources, (list, tuple)):
        raise ValueError("session_capabilities.application_sources must be a list")
    selected = registry.selected(application_id, active_sources=active_sources)
    command_records: List[CommandContribution] = list(
        _merged_records(registry.generic, selected, "commands")
    )
    surface_records: List[SurfaceContribution] = list(
        _merged_records(registry.generic, selected, "surfaces")
    )
    _require_unique_order("shell_command", command_records)
    _require_unique_order("shell_surface", surface_records)
    _require_unique_value("shell_command", (record.descriptor.id for record in command_records))
    _require_unique_value("shell_surface", (record.descriptor.id for record in surface_records))
    surface_ids = set(record.descriptor.id for record in surface_records)
    for record in command_records:
        _validate_dispatch(record)
        if record.descriptor.dispatch.get("kind") == "shell.surface":
            surface_id = str(record.descriptor.dispatch.get("surface_id") or "").strip()
            if surface_id not in surface_ids:
                raise ValueError("unknown_shell_surface:%s" % surface_id)
    for record in surface_records:
        _validate_renderer(record.descriptor.renderer_key, record.descriptor.id)

    tool_presentations = _merged_records(registry.generic, selected, "tool_presentations")
    timeline_items = _merged_records(registry.generic, selected, "timeline_items")
    interactions = _merged_records(registry.generic, selected, "interactions")
    _require_unique_value("shell_tool", (item.name for item in tool_presentations))
    _require_unique_value("shell_timeline_item", (item.event_kind for item in timeline_items))
    _require_unique_value("shell_interaction", (item.kind for item in interactions))
    for item in tool_presentations:
        _validate_renderer(item.renderer_key, item.name)
    for item in timeline_items:
        _validate_renderer(item.renderer_key, item.event_kind)
    for item in interactions:
        _validate_renderer(item.renderer_key, item.kind)

    active_ids = _active_command_ids(session_capabilities)
    commands = [
        record.descriptor
        for record in sorted(command_records, key=lambda item: (item.order, item.descriptor.id))
        if _command_is_available(record, active_ids)
    ]
    command_ids = {item.id for item in commands}
    keybindings = list(_merged_records(registry.generic, selected, "keybindings"))
    for item in keybindings:
        if item.command_id not in command_ids:
            raise ValueError("unknown_keybinding_command:%s" % item.command_id)
    return ShellDescriptor(
        schema_version=FRONTEND_PROTOCOL_SCHEMA_VERSION,
        commands=commands,
        surfaces=[
            record.descriptor
            for record in sorted(surface_records, key=lambda item: (item.order, item.descriptor.id))
        ],
        keybindings=keybindings,
        tool_presentations=list(tool_presentations),
        timeline_items=list(timeline_items),
        interactions=list(interactions),
    )
