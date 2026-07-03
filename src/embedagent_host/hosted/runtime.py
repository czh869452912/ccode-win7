from __future__ import annotations

from dataclasses import dataclass

from embedagent.context import ContextManager, make_context_config
from embedagent.project_memory import ProjectMemoryStore
from embedagent.session_store import SessionSummaryStore
from embedagent.tools import ToolRuntime
from embedagent_core.permissions import PermissionPolicy
from embedagent_host.hosted.launch_config import LaunchConfig
from embedagent_host.hosted.session_host import HostedSessionHost
from embedagent_host.inprocess_adapter import InProcessAdapter
from embedagent_host.providers.openai_compatible import OpenAICompatibleClient


@dataclass
class HostedRuntime(object):
    launch_config: LaunchConfig
    session_host: HostedSessionHost


def create_hosted_runtime(launch_config: LaunchConfig, event_handler=None) -> HostedRuntime:
    client = OpenAICompatibleClient(
        base_url=launch_config.base_url,
        api_key=launch_config.api_key,
        model=launch_config.model,
        timeout=launch_config.timeout,
    )
    tools = ToolRuntime(launch_config.workspace, app_config=launch_config.app_config)
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
        summary_store=SessionSummaryStore(launch_config.workspace),
        context_manager=context_manager,
        event_handler=event_handler,
        agent_application_id=launch_config.agent_application_id,
    )
    return HostedRuntime(
        launch_config=launch_config,
        session_host=HostedSessionHost(adapter=adapter),
    )
