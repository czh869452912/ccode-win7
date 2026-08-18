from __future__ import annotations

from dataclasses import dataclass

from embedagent_core.permissions import PermissionPolicy
from embedagent_protocol import (
    FrontendSessionPort,
    FrontendWorkspacePort,
)

from embedagent_host.frontend_ports import (
    InProcessFrontendSessionPort,
    InProcessFrontendWorkspacePort,
)
from embedagent_host.hosted.launch_config import LaunchConfig
from embedagent_host.inprocess_adapter import InProcessAdapter
from embedagent_host.providers.openai_compatible import OpenAICompatibleClient
from embedagent_host.runtime.context import ContextManager, make_context_config
from embedagent_host.runtime.project_memory import ProjectMemoryStore
from embedagent_host.runtime.session_store import SessionSummaryStore
from embedagent_host.runtime.tools import ToolRuntime


@dataclass
class HostedRuntime(object):
    launch_config: LaunchConfig
    session: FrontendSessionPort
    workspace: FrontendWorkspacePort

    def close(self) -> None:
        self.session.close()


def create_hosted_runtime(
    launch_config: LaunchConfig,
    event_sink=None,
    agent_application_registry=None,
    command_sanitizer_factory=None,
    bundle_root_resolver=None,
    system_prompt_builder=None,
) -> HostedRuntime:
    client = OpenAICompatibleClient(
        base_url=launch_config.base_url,
        api_key=launch_config.api_key,
        model=launch_config.model,
        timeout=launch_config.timeout,
    )
    tools = ToolRuntime(
        launch_config.workspace,
        app_config=launch_config.app_config,
        command_sanitizer_factory=command_sanitizer_factory,
        bundle_root_resolver=bundle_root_resolver,
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
    adapter = InProcessAdapter(
        client=client,
        tools=tools,
        max_turns=launch_config.max_turns,
        permission_policy=permission_policy,
        summary_store=SessionSummaryStore(
            launch_config.workspace,
            system_prompt_builder=system_prompt_builder,
        ),
        context_manager=context_manager,
        event_sink=event_sink,
        agent_application_id=launch_config.agent_application_id,
        agent_application_registry=agent_application_registry,
    )
    return HostedRuntime(
        launch_config=launch_config,
        session=InProcessFrontendSessionPort(adapter),
        workspace=InProcessFrontendWorkspacePort(adapter),
    )
