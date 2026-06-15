from __future__ import annotations

import pytest

from embedagent.extensions import (
    ExtensionContext,
    ExtensionManager,
    ToolRegistrationEvent,
    ToolRegistrationResult,
)
from embedagent.session import Action, AssistantReply, Observation, Session
from embedagent.tools import ToolDefinition, ToolRuntime


def dynamic_tool_metadata(permission_category="read", read_only=True):
    return {
        "permission_category": permission_category,
        "mode_visibility": ["build"],
        "workflow_visibility": ["chat"],
        "user_label": "Dynamic Echo",
        "progress_renderer_key": "default",
        "result_renderer_key": "default",
        "supports_diff_preview": False,
        "context_reducer_key": "dynamic_echo",
        "read_only": read_only,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "tool",
        "context_priority": 50,
    }


def make_dynamic_tool(name="dynamic_echo", permission_category="read", read_only=True):
    def handler(arguments):
        return Observation(
            name,
            True,
            None,
            {"echo": str(arguments.get("message") or "")},
        )

    return ToolDefinition(
        name=name,
        description="Echo a message from a dynamically registered tool.",
        parameters={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        handler=handler,
        metadata=dynamic_tool_metadata(permission_category, read_only=read_only),
        read_only=read_only,
        concurrency_safe=True,
        interrupt_behavior="block",
        result_budget_policy="compact-preview",
        activity_kind="tool",
        context_priority=50,
    )


def schema_names(schemas):
    return [item["function"]["name"] for item in schemas]


def test_register_tool_adds_schema_catalog_and_execution_metadata(tmp_path):
    runtime = ToolRuntime(str(tmp_path))
    runtime.register_tool(
        make_dynamic_tool(),
        source_id="test.extension",
        source_type="extension",
    )

    schemas = runtime.schemas_for("build", workflow_state="chat", tool_names=["dynamic_echo"])
    entry = runtime.tool_catalog_entry("dynamic_echo")
    observation = runtime.execute("dynamic_echo", {"message": "hello"})

    assert schema_names(schemas) == ["dynamic_echo"]
    assert entry["name"] == "dynamic_echo"
    assert entry["permission_category"] == "read"
    assert entry["source_type"] == "extension"
    assert entry["source_id"] == "test.extension"
    assert observation.success is True
    assert observation.data["echo"] == "hello"
    assert observation.data["tool_label"] == "Dynamic Echo"
    assert observation.data["permission_category"] == "read"


def test_register_tool_rejects_builtin_name_from_extension_source(tmp_path):
    runtime = ToolRuntime(str(tmp_path))
    tool = make_dynamic_tool(name="read_file")

    with pytest.raises(ValueError) as exc:
        runtime.register_tool(tool, source_id="test.extension", source_type="extension")

    assert "already registered" in str(exc.value)
    assert runtime.tool_catalog_entry("read_file")["source_type"] == "builtin"


def test_register_tool_is_idempotent_for_same_source(tmp_path):
    runtime = ToolRuntime(str(tmp_path))
    runtime.register_tool(
        make_dynamic_tool(),
        source_id="test.extension",
        source_type="extension",
    )
    runtime.register_tool(
        make_dynamic_tool(),
        source_id="test.extension",
        source_type="extension",
    )

    entries = [item for item in runtime.catalog_entries() if item.get("name") == "dynamic_echo"]

    assert len(entries) == 1
    assert entries[0]["source_id"] == "test.extension"


def test_builtin_and_harness_tools_have_source_metadata(tmp_path):
    from conftest import register_default_c_workflow_tools

    runtime = ToolRuntime(str(tmp_path))
    register_default_c_workflow_tools(runtime, str(tmp_path))

    assert runtime.tool_catalog_entry("read_file")["source_type"] == "builtin"
    assert runtime.tool_catalog_entry("read_file")["source_id"] == "embedagent.core"
    assert runtime.tool_catalog_entry("run_recipe")["source_type"] == "harness"
    assert runtime.tool_catalog_entry("run_recipe")["source_id"] == "embedagent.harness"


class DynamicToolExtension(object):
    extension_id = "dynamic_tools"
    builtin_extension = False

    def __init__(self, active=True, tool_name="dynamic_echo"):
        self.active = active
        self.tool_name = tool_name

    def register_tools(self, event, context):
        assert event.reason in ("session_start", "catalog", "test")
        assert context.tool_registry is not None
        return ToolRegistrationResult(
            tools=[make_dynamic_tool(name=self.tool_name)],
            source_id=self.extension_id,
        )

    def allowed_tool_names(self, mode_name, workflow_state="chat"):
        if self.active and mode_name == "build" and workflow_state == "chat":
            return {self.tool_name}
        return set()


class InvalidToolExtension(object):
    extension_id = "invalid_tool"
    builtin_extension = False

    def register_tools(self, event, context):
        del event, context
        return ToolRegistrationResult(tools=[object()], source_id=self.extension_id)


def test_extension_manager_registers_tools_into_runtime(tmp_path):
    runtime = ToolRuntime(str(tmp_path))
    manager = ExtensionManager([DynamicToolExtension()])

    manager.register_tools(
        ToolRegistrationEvent(current_mode="build", workflow_state_name="chat", reason="test"),
        ExtensionContext(workspace=str(tmp_path), tool_registry=runtime),
    )

    entry = runtime.tool_catalog_entry("dynamic_echo")
    assert entry["source_type"] == "extension"
    assert entry["source_id"] == "dynamic_tools"
    assert manager.diagnostics() == []


def test_extension_tool_registration_failure_records_diagnostic(tmp_path):
    runtime = ToolRuntime(str(tmp_path))
    manager = ExtensionManager([InvalidToolExtension()])

    manager.register_tools(
        ToolRegistrationEvent(current_mode="build", workflow_state_name="chat", reason="test"),
        ExtensionContext(workspace=str(tmp_path), tool_registry=runtime),
    )

    diagnostics = manager.diagnostics()
    assert diagnostics
    assert diagnostics[0]["extension_id"] == "invalid_tool"
    assert diagnostics[0]["event"] == "register_tools"
    assert diagnostics[0]["metadata"]["source_id"] == "invalid_tool"
    assert diagnostics[0]["metadata"]["reason"] == "test"


def test_agent_extension_host_registers_dynamic_tools_and_projects_active_schemas(tmp_path):
    from embedagent.agent_extension_host import AgentExtensionHost
    from embedagent.modes import allowed_tools_for
    from embedagent.permissions import PermissionPolicy

    runtime = ToolRuntime(str(tmp_path))
    session = Session()
    extension = DynamicToolExtension(active=True)
    host = AgentExtensionHost(
        manager=ExtensionManager([extension]),
        tools=runtime,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path)),
        mode_allowed_tools=allowed_tools_for,
    )

    host.register_tools(session, "build", "chat", reason="session_start")
    names = set(item["function"]["name"] for item in host.schemas_for_active_tools("build", "chat"))

    assert "dynamic_echo" in names
    assert runtime.tool_catalog_entry("dynamic_echo")["source_id"] == "dynamic_tools"


def test_agent_extension_host_uses_mode_contract_as_active_tool_fallback(tmp_path):
    from embedagent.agent_extension_host import AgentExtensionHost
    from embedagent.modes import allowed_tools_for
    from embedagent.permissions import PermissionPolicy

    runtime = ToolRuntime(str(tmp_path))
    host = AgentExtensionHost(
        manager=ExtensionManager(),
        tools=runtime,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path)),
        mode_allowed_tools=allowed_tools_for,
    )

    host.register_tools(Session(), "build", "chat", reason="session_start")
    names = set(item["function"]["name"] for item in host.schemas_for_active_tools("build", "chat"))

    assert "read_file" in names
    assert "write_file" in names
    assert "propose_mode_switch" in names


class ToolCallingClient(object):
    def __init__(self, action):
        self.action = action
        self.seen_tool_names = []

    def generate(self, messages, tools=None):
        del messages
        self.seen_tool_names = [
            item["function"]["name"] for item in list(tools or []) if item.get("type") == "function"
        ]
        return AssistantReply(
            content="using dynamic tool",
            actions=[self.action],
            finish_reason="tool_calls",
        )

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None:
            on_text_delta(reply.content)
        if on_reasoning_delta is not None:
            on_reasoning_delta(reply.reasoning_content)
        return reply


def test_query_engine_dynamic_tool_schema_requires_activation(tmp_path):
    from embedagent.permissions import PermissionPolicy
    from embedagent.query_engine import QueryEngine

    runtime = ToolRuntime(str(tmp_path))
    session = Session()
    inactive = DynamicToolExtension(active=False)
    engine = QueryEngine(
        client=ToolCallingClient(Action("dynamic_echo", {"message": "hi"}, "call-1")),
        tools=runtime,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path)),
        extension_manager=ExtensionManager([inactive]),
    )

    engine.initialize_session(session, "build", workflow_state="chat", user_text="hello")
    inactive_names = schema_names(engine._schemas_for_active_tools("build", "chat"))
    inactive.active = True
    active_names = schema_names(engine._schemas_for_active_tools("build", "chat"))

    assert "dynamic_echo" not in inactive_names
    assert "dynamic_echo" in active_names


def test_query_engine_executes_active_extension_tool(tmp_path):
    from embedagent.permissions import PermissionPolicy
    from embedagent.query_engine import QueryEngine

    action = Action("dynamic_echo", {"message": "hello"}, "call-dynamic")
    client = ToolCallingClient(action)
    engine = QueryEngine(
        client=client,
        tools=ToolRuntime(str(tmp_path)),
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path)),
        extension_manager=ExtensionManager([DynamicToolExtension(active=True)]),
        max_turns=1,
    )

    result = engine.submit_user_turn("use dynamic", stream=False, initial_mode="build")
    observation = result.session.turns[-1].observations[-1]

    assert "dynamic_echo" in client.seen_tool_names
    assert observation.success is True
    assert observation.tool_name == "dynamic_echo"
    assert observation.data["echo"] == "hello"


def test_agent_tool_action_service_executes_active_dynamic_tool(tmp_path):
    from embedagent.agent_extension_host import AgentExtensionHost
    from embedagent.agent_tool_action_service import AgentToolActionService
    from embedagent.permissions import PermissionPolicy
    from embedagent.query_engine import QueryEngine

    runtime = ToolRuntime(str(tmp_path))
    policy = PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path))
    host = AgentExtensionHost(
        manager=ExtensionManager([DynamicToolExtension(active=True)]),
        tools=runtime,
        permission_policy=policy,
    )
    session = Session()
    host.register_tools(session, "build", "chat", reason="session_start")
    service = AgentToolActionService(
        tools=runtime,
        permission_policy=policy,
        extension_host=host,
        app_config_provider=lambda: None,
        failure_observation_factory=QueryEngine(
            client=ToolCallingClient(Action("dynamic_echo", {"message": "hi"}, "call-client")),
            tools=runtime,
            permission_policy=policy,
        )._failure_observation,
    )

    observation, current_mode, suspended = service.execute_action(
        session,
        Action("dynamic_echo", {"message": "hello"}, "call-dynamic"),
        "build",
        "chat",
        permission_handler=None,
        user_input_handler=None,
    )

    assert suspended is None
    assert current_mode == "build"
    assert observation.success is True
    assert observation.data["echo"] == "hello"


class DynamicShellExtension(DynamicToolExtension):
    extension_id = "dynamic_shell"

    def register_tools(self, event, context):
        del event, context
        return ToolRegistrationResult(
            tools=[
                make_dynamic_tool(
                    name="dynamic_shell",
                    permission_category="shell_exec",
                    read_only=False,
                )
            ],
            source_id=self.extension_id,
        )


def test_query_engine_dynamic_shell_tool_waits_for_permission(tmp_path):
    from embedagent.permissions import PermissionPolicy
    from embedagent.query_engine import QueryEngine

    action = Action("dynamic_shell", {"message": "hello"}, "call-shell")
    engine = QueryEngine(
        client=ToolCallingClient(action),
        tools=ToolRuntime(str(tmp_path)),
        permission_policy=PermissionPolicy(auto_approve_all=False, workspace=str(tmp_path)),
        extension_manager=ExtensionManager(
            [DynamicShellExtension(active=True, tool_name="dynamic_shell")]
        ),
        max_turns=1,
    )

    result = engine.submit_user_turn("use dynamic shell", stream=False, initial_mode="build")

    assert result.transition.reason == "permission_wait"
    assert result.pending_interaction is not None
    assert result.pending_interaction.tool_name == "dynamic_shell"
    assert result.pending_interaction.request_payload["permission"]["category"] == "shell_exec"


def test_inprocess_adapter_catalog_includes_active_extension_tool(tmp_path):
    from embedagent.inprocess_adapter import InProcessAdapter

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    adapter.extension_manager.register(DynamicToolExtension(active=True))

    catalog = adapter.get_tool_catalog()
    entry = [item for item in catalog if item.get("name") == "dynamic_echo"][0]

    assert entry["source_type"] == "extension"
    assert entry["source_id"] == "dynamic_tools"
    assert entry["permission_category"] == "read"


def test_dynamic_tool_registration_accepts_network_and_telemetry_categories(tmp_path):
    runtime = ToolRuntime(str(tmp_path))

    runtime.register_tool(
        make_dynamic_tool(
            name="intranet_fetch",
            permission_category="network",
            read_only=False,
        ),
        source_type="extension",
        source_id="enterprise_tools",
    )
    runtime.register_tool(
        make_dynamic_tool(
            name="flush_telemetry",
            permission_category="telemetry",
            read_only=False,
        ),
        source_type="extension",
        source_id="enterprise_tools",
    )

    assert runtime.tool_catalog_entry("intranet_fetch")["permission_category"] == "network"
    assert runtime.tool_catalog_entry("flush_telemetry")["permission_category"] == "telemetry"
