"""Product composition for the standalone Host distribution."""

from __future__ import annotations

from typing import Any

from embedagent_core import ApplicationRegistrar
from embedagent_core.permissions import PermissionPolicy
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
from embedagent_host.inprocess_adapter import InProcessAdapter
from embedagent_host.providers.openai_compatible import OpenAICompatibleClient
from embedagent_host.runtime.agent_applications import (
    ApplicationRuntimeContributionRegistry,
    application_registry_from_runtime_contributions,
)
from embedagent_host.runtime.context import ContextManager, make_context_config
from embedagent_host.runtime.project_memory import ProjectMemoryStore
from embedagent_host.runtime.session_store import SessionSummaryStore
from embedagent_host.runtime.tools import ToolRuntime

from embedagent.application_loader import load_selected_applications
from embedagent.bundle_policy import load_current_bundle_policy
from embedagent.command_sanitizer import get_command_sanitizer
from embedagent.config import load_config
from embedagent.di_container import get_default_container
from embedagent.frontend.shell.registration import ShellContributionRegistry
from embedagent.modes import build_system_prompt
from embedagent.product_catalog import product_agent_application_registry
from embedagent.runtime_discovery import discover_bundle_root


def get_inprocess_adapter(fresh: bool = False):
    return get_default_container().resolve("inprocess_adapter", fresh=fresh)


get_default_container().register_factory("inprocess_adapter", lambda: InProcessAdapter)


def _current_bundle_policy():
    return load_current_bundle_policy(__file__)


def resolve_launch_config(workspace: str, overrides: LaunchOverrides) -> LaunchConfig:
    launch_config = resolve_generic_launch_config(
        workspace,
        overrides,
        config_loader=load_config,
    )
    policy = _current_bundle_policy()
    launch_config.agent_application_id = policy.require_application(
        launch_config.agent_application_id
    )
    return launch_config


def selected_application_registry(policy):
    """Build the application registry from the selected plugin entries."""
    allowed_ids = policy.allowed_agent_application_ids if policy.bundled else None
    if policy.bundled and policy.registration_entries:

        class _NoopExtensionHost(object):
            def register(self, extension, source_id):
                del extension, source_id
                return lambda: None

            def register_prompt_provider(self, provider, source_id):
                del provider, source_id
                return lambda: None

            def register_context_provider(self, provider, source_id):
                del provider, source_id
                return lambda: None

        runtime_registry = ApplicationRuntimeContributionRegistry()
        registrar = ApplicationRegistrar(
            _NoopExtensionHost(),
            ShellContributionRegistry(),
            runtime_registry,
        )
        load_disposer = load_selected_applications(
            {
                "allowed_agent_application_ids": policy.allowed_agent_application_ids,
                "registration_entries": policy.registration_entries,
            },
            registrar,
        )
        try:
            return application_registry_from_runtime_contributions(
                runtime_registry.contributions(),
                default_application_id=policy.allowed_agent_application_ids[0],
            )
        finally:
            load_disposer()
    return product_agent_application_registry(allowed_ids)


def create_hosted_runtime(
    launch_config: LaunchConfig,
    event_sink: Any = None,
) -> HostedRuntime:
    policy = _current_bundle_policy()
    launch_config.agent_application_id = policy.require_application(
        launch_config.agent_application_id
    )
    selected_registry = selected_application_registry(policy)
    model_client = OpenAICompatibleClient(
        base_url=launch_config.base_url,
        api_key=launch_config.api_key,
        model=launch_config.model,
        timeout=launch_config.timeout,
    )
    tool_runtime = ToolRuntime(
        launch_config.workspace,
        app_config=launch_config.app_config,
        command_sanitizer_factory=get_command_sanitizer,
        bundle_root_resolver=discover_bundle_root,
    )
    context_manager = ContextManager(
        config=make_context_config(launch_config.app_config),
        project_memory=ProjectMemoryStore(launch_config.workspace),
    )
    permission_policy = PermissionPolicy(
        auto_approve_all=launch_config.approve_all,
        auto_approve_writes=launch_config.approve_writes,
        auto_approve_commands=launch_config.approve_commands,
        workspace=launch_config.workspace,
        rules_path=launch_config.permission_rules,
    )
    summary_store = SessionSummaryStore(
        launch_config.workspace,
        system_prompt_builder=build_system_prompt,
    )
    return create_generic_hosted_runtime(
        launch_config,
        model_client=model_client,
        tool_runtime=tool_runtime,
        context_manager=context_manager,
        permission_policy=permission_policy,
        summary_store=summary_store,
        event_sink=event_sink,
        agent_application_registry=selected_registry,
    )
