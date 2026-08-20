from __future__ import annotations

from dataclasses import dataclass

from embedagent_core import ApplicationConfigurationError
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


@dataclass
class HostedRuntime(object):
    launch_config: LaunchConfig
    session: FrontendSessionPort
    workspace: FrontendWorkspacePort

    def close(self) -> None:
        self.session.close()


def create_hosted_runtime(
    launch_config: LaunchConfig,
    model_client=None,
    tool_runtime=None,
    context_manager=None,
    permission_policy=None,
    summary_store=None,
    event_sink=None,
    agent_application_registry=None,
) -> HostedRuntime:
    required = {
        "model_client": model_client,
        "tool_runtime": tool_runtime,
        "context_manager": context_manager,
        "permission_policy": permission_policy,
        "summary_store": summary_store,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise ApplicationConfigurationError(
            "host runtime collaborators are required: %s" % ",".join(missing)
        )
    adapter = InProcessAdapter(
        client=model_client,
        tools=tool_runtime,
        max_turns=launch_config.max_turns,
        permission_policy=permission_policy,
        summary_store=summary_store,
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
