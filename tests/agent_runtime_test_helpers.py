from __future__ import annotations

import threading
from typing import Any

from embedagent_core.api import AgentPorts, ApplicationRuntimePolicy, RuntimeDefinition
from embedagent_core.permissions import PermissionPolicy
from embedagent_core.ports import NoopContextAssembler
from embedagent_core.runner import AgentRuntime
from embedagent_core.session import Session
from embedagent_core.session_log import InMemorySessionLog
from embedagent_core.session_reducer import SessionReducerContext
from embedagent_host.runtime.agent_applications import build_agent_application
from embedagent_host.runtime.context import ContextManager
from embedagent_host.runtime.project_memory import ProjectMemoryStore
from embedagent_host.runtime.transcript_store import TranscriptStore
from embedagent_host.runtime.workspace_intelligence import WorkspaceIntelligenceBroker

from embedagent.bundle_policy import BundleRuntimePolicy
from embedagent.hosted import selected_application_registry
from embedagent.modes import (
    allowed_tools_for,
    build_system_prompt,
    is_path_writable,
    parse_mode_command,
    parse_natural_language_mode_switch,
    require_mode,
)


class ProductModeToolPolicy(object):
    def allowed_tools_for(self, mode_name: str, workflow_state: Any = None):
        del workflow_state
        return allowed_tools_for(mode_name)


class ProductWritePathPolicy(object):
    def is_path_writable(self, mode_name: str, normalized_path: str, app_config: Any = None):
        return is_path_writable(mode_name, normalized_path, app_config)


class ProductModeRuntimePolicy(object):
    def default_mode(self):
        return "explore"

    def require_mode(self, mode_name: str):
        return require_mode(mode_name or self.default_mode())

    def build_system_prompt(
        self,
        mode_name: str,
        app_config: Any = None,
        workspace: str = "",
        local_resources: Any = None,
    ):
        return build_system_prompt(
            mode_name,
            app_config,
            workspace,
            local_resources=local_resources,
        )

    def parse_mode_switch_request(self, user_text: str, fallback_mode: str):
        mode_name, remainder, switched = parse_mode_command(
            user_text,
            fallback_mode=fallback_mode,
        )
        if switched:
            return mode_name, remainder, True
        return parse_natural_language_mode_switch(user_text, fallback_mode=fallback_mode)


def build_product_agent_application(tools):
    return build_agent_application(
        "",
        tools,
        registry=cpp_application_registry(),
    )


def cpp_application_registry():
    return selected_application_registry(
        BundleRuntimePolicy(
            bundled=True,
            flavor_id="cpp-desktop",
            allowed_agent_application_ids=("embedagent.default_c_cpp",),
            shell_ids=("cli", "tui", "gui"),
            registration_entries=(
                "embedagent.product_catalog:register",
                "embedagent_workflow_cpp.application:register_application",
            ),
        )
    )


class BoundRuntimeDispatcher(object):
    """Test-only adapter that binds reducer context around dispatcher calls."""

    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime
        self._contexts = {}
        self._lock = threading.Lock()

    def __setattr__(self, name, value):
        if name in ("runtime", "_contexts", "_lock") or "runtime" not in self.__dict__:
            object.__setattr__(self, name, value)
            return
        dispatcher = self.runtime.dispatcher
        if hasattr(dispatcher, name):
            setattr(dispatcher, name, value)
            return
        object.__setattr__(self, name, value)

    def __getattr__(self, name):
        target = getattr(self.runtime.dispatcher, name)
        if not callable(target):
            return target

        def invoke(*args, **kwargs):
            session = kwargs.get("session")
            if not isinstance(session, Session):
                session = next((item for item in args if isinstance(item, Session)), None)
            key = id(session) if session is not None else 0
            with self._lock:
                context = self._contexts.get(key)
                if context is None:
                    context = SessionReducerContext(
                        current_mode=self.runtime.definition.application_policy.default_mode
                    )
                    self._contexts[key] = context
            with self.runtime.event_committer.bind(context):
                return target(*args, **kwargs)

        return invoke


def build_agent_runtime_dispatcher(
    client,
    tools,
    permission_policy=None,
    extension_manager=None,
    context_manager=None,
    transcript_store=None,
    definition=None,
    session_projection=None,
    max_parallel_tools=3,
    max_turns=None,
):
    policy = permission_policy or PermissionPolicy()
    runtime = AgentRuntime(
        AgentPorts(
            model=client,
            tools=tools,
            session_log=transcript_store or InMemorySessionLog(),
            context=context_manager or NoopContextAssembler(),
            permissions=policy,
            session_projection=session_projection,
            extension_manager=extension_manager,
        ),
        definition or RuntimeDefinition(max_turns=max_turns),
    )
    runtime.dispatcher.max_parallel_tools = max(1, int(max_parallel_tools or 1))
    return BoundRuntimeDispatcher(runtime)


def build_product_agent_runtime_dispatcher(
    client,
    tools,
    workspace: str = "",
    permission_policy=None,
    extension_manager=None,
    context_manager=None,
    project_memory_store=None,
    intelligence_broker=None,
    **kwargs: Any,
):
    workspace = str(workspace or getattr(tools, "workspace", "") or ".")
    project_memory = project_memory_store or ProjectMemoryStore(workspace)
    transcript_store = kwargs.pop("transcript_store", None) or TranscriptStore(workspace)
    max_parallel_tools = int(kwargs.pop("max_parallel_tools", 3) or 3)
    session_projection = kwargs.pop("session_projection", None)
    manager = extension_manager
    if manager is None:
        manager = build_product_agent_application(tools).extension_manager
    policy = permission_policy or PermissionPolicy(
        auto_approve_all=True,
        workspace=workspace,
    )
    context = context_manager or ContextManager(
        project_memory=project_memory,
        workspace=workspace,
        intelligence_broker=intelligence_broker or WorkspaceIntelligenceBroker.default(),
    )
    definition = RuntimeDefinition(
        max_turns=kwargs.pop("max_turns", None),
        application_policy=ApplicationRuntimePolicy(
            default_mode="explore",
            mode_tool_policy=kwargs.pop("mode_tool_policy", ProductModeToolPolicy()),
            write_path_policy=kwargs.pop("write_path_policy", ProductWritePathPolicy()),
            mode_runtime_policy=kwargs.pop("mode_runtime_policy", ProductModeRuntimePolicy()),
        ),
    )
    if kwargs:
        raise TypeError("unsupported runtime test options: %s" % sorted(kwargs))
    runtime = AgentRuntime(
        AgentPorts(
            model=client,
            tools=tools,
            session_log=transcript_store,
            context=context,
            permissions=policy,
            session_projection=session_projection,
            extension_manager=manager,
        ),
        definition,
    )
    runtime.dispatcher.max_parallel_tools = max_parallel_tools
    return BoundRuntimeDispatcher(runtime)
