"""Product composition for the standalone Host distribution."""

from __future__ import annotations

from typing import Any

from embedagent_host.hosted.launch_config import (
    LaunchConfig,
    LaunchOverrides,
)
from embedagent_host.hosted.launch_config import (
    resolve_launch_config as resolve_generic_launch_config,
)
from embedagent_host.hosted.runtime import (
    HostedRuntime,
)
from embedagent_host.hosted.runtime import (
    create_hosted_runtime as create_generic_hosted_runtime,
)

from embedagent.agent_application_registry import product_agent_application_registry
from embedagent.command_sanitizer import get_command_sanitizer
from embedagent.config import load_config
from embedagent.modes import build_system_prompt
from embedagent.runtime_discovery import discover_bundle_root


def resolve_launch_config(workspace: str, overrides: LaunchOverrides) -> LaunchConfig:
    return resolve_generic_launch_config(
        workspace,
        overrides,
        config_loader=load_config,
    )


def create_hosted_runtime(
    launch_config: LaunchConfig,
    event_handler: Any = None,
) -> HostedRuntime:
    return create_generic_hosted_runtime(
        launch_config,
        event_handler=event_handler,
        agent_application_registry=product_agent_application_registry(),
        command_sanitizer_factory=get_command_sanitizer,
        bundle_root_resolver=discover_bundle_root,
        system_prompt_builder=build_system_prompt,
    )
