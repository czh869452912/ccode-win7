from __future__ import annotations

from typing import Optional

from embedagent_core.agent_extension_host import AgentExtensionHost
from embedagent_core.agent_kernel import AgentKernel
from embedagent_core.agent_lifecycle import AgentLifecycleJournal
from embedagent_core.agent_loop import AgentLoop
from embedagent_core.agent_loop_continuation import DefaultAgentLoopContinuationPolicy
from embedagent_core.agent_tool_action_service import AgentToolActionService, InteractionFactory
from embedagent_core.api import (
    AgentObserver,
    AgentPorts,
    AgentResult,
    CancelToken,
    RuntimeDefinition,
)
from embedagent_core.extensions import ExtensionManager
from embedagent_core.prompt_assembly_service import PromptAssemblyService
from embedagent_core.provider_step_service import ProviderStepService
from embedagent_core.session_input import SessionEventCommitter, SessionInputDispatcher
from embedagent_core.session_journal import SessionJournal
from embedagent_core.session_reducer import SessionReducer
from embedagent_core.session_transaction import (
    AgentRequest,
    SessionTransaction,
)
from embedagent_core.session_transaction import (
    SessionRecoveryRequired as SessionRecoveryRequired,
)
from embedagent_core.turn_snapshot_service import TurnSnapshotService


class AgentRuntime(object):
    def __init__(self, ports: AgentPorts, definition: RuntimeDefinition) -> None:
        self.ports = ports
        self.definition = definition
        self.extension_manager = ports.extension_manager or ExtensionManager(
            list(definition.extensions)
        )
        self.reducer = SessionReducer()
        self.journal = SessionJournal(ports.session_log, self.reducer)
        self.event_committer = SessionEventCommitter(ports.session_log, self.journal)
        self.extension_host = AgentExtensionHost(
            manager=self.extension_manager,
            tools=ports.tools,
            permission_policy=ports.permissions,
            mode_tool_policy=definition.application_policy.mode_tool_policy,
        )
        self.extension_manager.register_context_reducers(ports.context.reducers)
        category_setter = getattr(ports.permissions, "set_category_lookup", None)
        if callable(category_setter):
            category_setter(lambda tool_name: _tool_permission_category(ports.tools, tool_name))
        self.tool_actions = AgentToolActionService(
            tools=ports.tools,
            permission_policy=ports.permissions,
            extension_host=self.extension_host,
            app_config_provider=lambda: getattr(ports.tools, "app_config", None),
            interaction_factory=InteractionFactory(),
            write_path_policy=definition.application_policy.write_path_policy,
        )
        self.provider_steps = ProviderStepService(
            context_assembler=ports.context,
            extension_host=self.extension_host,
            snapshot_service=TurnSnapshotService(),
            tools=ports.tools,
            client=ports.model,
            session_log=ports.session_log,
        )
        self.lifecycle = AgentLifecycleJournal(
            append_event=self.event_committer.append_raw,
            session_guard=self.event_committer.guard,
            commit_transition=lambda session, payload: self.event_committer.commit(
                session, "loop_transition", payload
            ),
        )
        self.kernel = AgentKernel(lifecycle=self.lifecycle)
        self.loop = AgentLoop(
            self.kernel,
            self.journal,
            self.provider_steps,
            self.tool_actions,
            DefaultAgentLoopContinuationPolicy(),
        )
        self.dispatcher = SessionInputDispatcher(
            tools=ports.tools,
            event_committer=self.event_committer,
            lifecycle=self.lifecycle,
            kernel=self.kernel,
            agent_loop=self.loop,
            provider_steps=self.provider_steps,
            action_service=self.tool_actions,
            extension_host=self.extension_host,
            prompt_assembly=PromptAssemblyService(),
            max_turns=definition.max_turns,
            permission_policy=ports.permissions,
            context_manager=ports.context,
            session_projection=ports.session_projection,
            transcript_store=ports.session_log,
            mode_tool_policy=definition.application_policy.mode_tool_policy,
            write_path_policy=definition.application_policy.write_path_policy,
            mode_runtime_policy=definition.application_policy.mode_runtime_policy,
        )
        self.transaction = SessionTransaction(
            ports.session_log,
            self.journal,
            self.loop,
            definition,
            ports.session_projection,
            self.dispatcher,
            self.event_committer,
            restore_policy=ports.restore_policy,
        )


def _tool_permission_category(tools, tool_name: str) -> str:
    lookup = getattr(tools, "tool_catalog_entry", None)
    if not callable(lookup):
        return ""
    entry = lookup(tool_name) or {}
    if not isinstance(entry, dict):
        return ""
    return str(entry.get("permission_category") or "")


def run_agent(
    runtime: AgentRuntime,
    request: AgentRequest,
    observer: Optional[AgentObserver] = None,
    cancel: Optional[CancelToken] = None,
) -> AgentResult:
    return runtime.transaction.submit(request, observer=observer, cancel=cancel)
