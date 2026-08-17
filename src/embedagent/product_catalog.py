from __future__ import annotations

from typing import Any, Iterable, Optional, Tuple

from embedagent_host.runtime.agent_applications import (
    BUILTIN_AGENT_APPLICATION_RECORDS,
    GENERIC_AGENT_APPLICATION_ID,
    AgentApplicationRegistry,
    runtime_contribution_for_record,
)

from embedagent.frontend.shell.defaults import (
    desktop_file_contribution,
    minimal_shell_contribution,
    preview_contribution,
    source_control_contribution,
    terminal_contribution,
)
from embedagent.frontend.shell.registration import ShellContribution, ShellContributionRegistry


def product_agent_application_registry(
    allowed_application_ids: Optional[Tuple[str, ...]] = None,
) -> AgentApplicationRegistry:
    records = tuple(BUILTIN_AGENT_APPLICATION_RECORDS)
    if allowed_application_ids is None:
        return AgentApplicationRegistry(
            application_records=records,
            default_application_id=GENERIC_AGENT_APPLICATION_ID,
        )

    allowed = tuple(str(item or "").strip() for item in allowed_application_ids)
    known_ids = tuple(record.application_id for record in records)
    if not allowed or any(not item for item in allowed) or len(allowed) != len(set(allowed)):
        raise ValueError("Allowed agent applications must contain unique nonempty ids")
    unknown = tuple(item for item in allowed if item not in known_ids)
    if unknown:
        raise ValueError("Unknown allowed agent application %r" % (unknown[0],))
    selected = tuple(record for record in records if record.application_id in allowed)
    if not selected:
        raise ValueError("Allowed agent applications did not select a product application")
    return AgentApplicationRegistry(
        application_records=selected,
        default_application_id=allowed[0],
    )


def _merge_shell_contributions(
    contributions: Iterable[ShellContribution],
) -> ShellContribution:
    records = tuple(contributions)
    return ShellContribution(
        commands=tuple(item for record in records for item in record.commands),
        surfaces=tuple(item for record in records for item in record.surfaces),
        keybindings=tuple(item for record in records for item in record.keybindings),
        tool_presentations=tuple(item for record in records for item in record.tool_presentations),
        timeline_items=tuple(item for record in records for item in record.timeline_items),
        interactions=tuple(item for record in records for item in record.interactions),
    )


def product_shell_registry() -> ShellContributionRegistry:
    generic = _merge_shell_contributions(
        (
            minimal_shell_contribution(),
            desktop_file_contribution(),
            terminal_contribution(),
            source_control_contribution(),
            preview_contribution(),
        )
    )
    applications = dict(
        (record.application_id, ShellContribution()) for record in BUILTIN_AGENT_APPLICATION_RECORDS
    )
    return ShellContributionRegistry(generic=generic, applications=applications)


def product_shell_compiler():
    registry = product_shell_registry()

    def compile_descriptor(application_id, session_capabilities):
        return registry.compile(application_id, session_capabilities)

    return compile_descriptor


def register(registrar: Any):
    """Register the generic product shell contribution through a plugin sink."""
    contribution = product_shell_registry().generic
    generic_record = next(
        record
        for record in BUILTIN_AGENT_APPLICATION_RECORDS
        if record.application_id == GENERIC_AGENT_APPLICATION_ID
    )
    runtime_disposer = registrar.add_runtime_contribution(
        runtime_contribution_for_record(generic_record),
        "embedagent.product_catalog",
    )
    shell_disposer = registrar.add_shell_contribution(contribution, "embedagent.product_catalog")

    def dispose() -> None:
        shell_disposer()
        runtime_disposer()

    return dispose
