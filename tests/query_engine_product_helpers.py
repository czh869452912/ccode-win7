from __future__ import annotations

from typing import Any

from embedagent_core.permissions import PermissionPolicy
from embedagent_core.query_engine import QueryEngine as CoreQueryEngine
from embedagent_host.runtime.agent_applications import build_agent_application
from embedagent_host.runtime.context import ContextManager
from embedagent_host.runtime.project_memory import ProjectMemoryStore
from embedagent_host.runtime.transcript_store import TranscriptStore
from embedagent_host.runtime.workspace_intelligence import WorkspaceIntelligenceBroker

from embedagent.modes import (
    allowed_tools_for,
    build_system_prompt,
    is_path_writable,
    parse_mode_command,
    parse_natural_language_mode_switch,
    require_mode,
)
from embedagent.product_catalog import product_agent_application_registry


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
    return build_agent_application("", tools, registry=product_agent_application_registry())


def build_product_query_engine(
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
    manager = extension_manager
    if manager is None:
        manager = build_product_agent_application(tools).extension_manager
    return CoreQueryEngine(
        client=client,
        tools=tools,
        permission_policy=permission_policy
        or PermissionPolicy(auto_approve_all=True, workspace=workspace),
        context_manager=context_manager
        or ContextManager(
            project_memory=project_memory,
            workspace=workspace,
            intelligence_broker=intelligence_broker or WorkspaceIntelligenceBroker(),
        ),
        transcript_store=transcript_store,
        extension_manager=manager,
        mode_tool_policy=kwargs.pop("mode_tool_policy", ProductModeToolPolicy()),
        write_path_policy=kwargs.pop("write_path_policy", ProductWritePathPolicy()),
        mode_runtime_policy=kwargs.pop("mode_runtime_policy", ProductModeRuntimePolicy()),
        **kwargs,
    )
