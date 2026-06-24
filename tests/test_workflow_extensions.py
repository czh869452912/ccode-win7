import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

from embedagent.session import AssistantReply, Session

_REPO_ROOT = Path(__file__).resolve().parent.parent


class DoneClient(object):
    def generate(self, messages, tools=None):
        del messages, tools
        return AssistantReply(content="done", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        if on_reasoning_delta is not None and reply.reasoning_content:
            on_reasoning_delta(reply.reasoning_content)
        return reply


class FakeWorkflowExtension(object):
    def before_agent_start(self, event, context):
        del event, context
        from embedagent.extensions import PromptPatch

        return PromptPatch(
            prompt_units=["fake prompt"],
            active_tool_names=["fake_tool"],
            metadata={"source": "fake"},
        )


class CatalogExtension(object):
    def allowed_tool_names(self, mode_name, workflow_state="chat"):
        del workflow_state
        if mode_name == "build":
            return {"git_diff"}
        return set()


class ManifestExtension(object):
    extension_id = "fake.workflow"
    builtin_extension = False

    def package_manifest(self):
        return {
            "package_id": "fake.workflow",
            "label": "Fake Workflow",
            "source_type": "project",
            "source_id": "fake.workflow",
            "tools": [],
            "packs": [],
        }


class ToolRuntimeBoundaryProbe(object):
    workspace = "."
    tool_result_store = None
    projection_db = None
    app_config = None

    def describe_mode(
        self,
        mode_name,
        workflow_state="chat",
        current_phase="",
        observations=None,
    ):
        from embedagent.harness.runner import HarnessRunner

        return HarnessRunner().describe_mode(
            mode_name,
            current_phase=current_phase,
            observations=observations,
        )

    def schemas_for(self, mode_name, workflow_state="chat", tool_names=None):
        del mode_name, workflow_state
        requested = set(tool_names or [])
        return [
            {
                "type": "function",
                "function": {"name": name, "parameters": {"type": "object"}},
            }
            for name in sorted(requested)
        ]

    def allowed_tool_names(self, mode_name, workflow_state="chat"):
        del mode_name, workflow_state
        raise AssertionError("QueryEngine should not use runtime harness pack fallback")


def test_fake_workflow_extension_adds_prompt_units_and_active_tools():
    from embedagent.extensions import ExtensionContext, ExtensionManager, SessionView, WorkflowEvent

    manager = ExtensionManager()
    manager.register(FakeWorkflowExtension())
    session = Session()

    patch = manager.before_agent_start(
        WorkflowEvent(
            session_id=session.session_id,
            current_mode="build",
            user_text="build it",
        ),
        ExtensionContext(
            workspace=".",
            session_view=SessionView.from_session(session),
        ),
    )

    assert patch.prompt_units == ["fake prompt"]
    assert patch.active_tool_names == ["fake_tool"]
    assert patch.metadata == {"source": "fake"}


def test_extension_manager_collects_package_manifests_from_extensions():
    from embedagent.extensions import ExtensionManager

    manager = ExtensionManager([ManifestExtension()])

    manifests = manager.package_manifests()

    assert manifests == [
        {
            "package_id": "fake.workflow",
            "label": "Fake Workflow",
            "source_type": "project",
            "source_id": "fake.workflow",
            "tools": [],
            "packs": [],
        }
    ]


def test_session_has_generic_workflow_state():
    session = Session()

    session.workflow_state["workflow"] = {"id": "fake", "state": "active"}

    assert session.workflow_state["workflow"]["id"] == "fake"


def test_session_no_longer_has_task_graph_field():
    from dataclasses import fields

    from embedagent.session import Session

    assert "task_graph" not in {field.name for field in fields(Session)}
    assert not hasattr(Session(), "task_graph")


def test_session_import_does_not_eagerly_load_harness_task_graph():
    script = (
        "import sys\n"
        "import embedagent.session\n"
        "print('embedagent.harness.task_graph' in sys.modules)\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(_REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=True,
    )

    assert result.stdout.strip() == "False"


def test_c_harness_extension_preserves_build_prompt_behavior(tmp_path):
    from embedagent.default_extensions import build_default_extension_set
    from embedagent.permissions import PermissionPolicy
    from embedagent.query_engine import QueryEngine
    from embedagent.tools import ToolRuntime

    tools = ToolRuntime(str(tmp_path))
    default_extensions = build_default_extension_set(tools)
    engine = QueryEngine(
        client=DoneClient(),
        tools=tools,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path)),
        extension_manager=default_extensions.manager,
    )

    result = engine.submit_user_turn(
        user_text="build the project",
        stream=False,
        initial_mode="build",
    )
    contents = [
        message.content for message in result.session.messages if message.kind == "workflow_prompt"
    ]

    assert any("Mode: build" in item for item in contents)
    assert any("Discipline: lite_spec_tdd" in item for item in contents)
    assert not any("Core pack:" in item for item in contents)


def test_c_harness_extension_uses_generic_workflow_prompt_kind(tmp_path):
    from embedagent.default_extensions import build_default_extension_set
    from embedagent.permissions import PermissionPolicy
    from embedagent.query_engine import QueryEngine
    from embedagent.tools import ToolRuntime

    tools = ToolRuntime(str(tmp_path))
    default_extensions = build_default_extension_set(tools)
    engine = QueryEngine(
        client=DoneClient(),
        tools=tools,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path)),
        extension_manager=default_extensions.manager,
    )

    result = engine.submit_user_turn(
        user_text="build the project",
        stream=False,
        initial_mode="build",
    )
    prompt_kinds = [
        message.kind
        for message in result.session.messages
        if message.role == "system" and "Mode: build" in message.content
    ]

    assert "workflow_prompt" in prompt_kinds
    assert "harness_prompt" not in prompt_kinds


def test_workflow_prompt_descriptor_uses_generic_name():
    extensions_source = (_REPO_ROOT / "src" / "embedagent" / "extensions.py").read_text(
        encoding="utf-8"
    )
    harness_source = (_REPO_ROOT / "src" / "embedagent" / "harness" / "extension.py").read_text(
        encoding="utf-8"
    )

    assert "class WorkflowPrompt" in extensions_source
    assert "HarnessPrompt = WorkflowPrompt" in extensions_source
    assert "HarnessPrompt(" not in harness_source
    assert "from embedagent.extensions import HarnessPrompt" not in harness_source


def test_c_harness_workflow_projection_builder_shapes_generic_payload():
    from embedagent.harness.task_graph import TaskGraph
    from embedagent.harness.workflow_projection import build_c_harness_workflow_projection

    graph = TaskGraph.from_user_request("build the project", "build")
    context = type(
        "Context",
        (),
        {
            "task_summary": "context summary",
            "task_items": [{"id": "context-task", "title": "Context task"}],
            "current_phase": "context-phase",
            "discipline_label": "context-discipline",
            "current_activity": "context activity",
        },
    )()

    workflow = build_c_harness_workflow_projection(graph, context=context)

    assert workflow["id"] == "c_harness"
    assert workflow["label"] == "C Harness"
    assert workflow["state"] == "active"
    assert workflow["summary"] == "context summary"
    assert workflow["items"] == [{"id": "context-task", "title": "Context task"}]
    assert workflow["activity"] == "context activity"
    assert workflow["metadata"] == {
        "current_phase": "context-phase",
        "discipline_profile": "context-discipline",
    }


def test_c_harness_extension_delegates_workflow_projection_to_builder():
    source = (_REPO_ROOT / "src" / "embedagent" / "harness" / "extension.py").read_text(
        encoding="utf-8"
    )

    assert "build_c_harness_workflow_projection" in source
    assert '"id": "c_harness"' not in source


def test_query_engine_no_longer_imports_task_graph_directly():
    source = (_REPO_ROOT / "src" / "embedagent" / "query_engine.py").read_text(encoding="utf-8")

    assert "from embedagent.harness.task_graph import TaskGraph" not in source
    assert "TaskGraph.from_user_request" not in source


def test_c_harness_extension_no_longer_reads_session_task_graph_directly():
    source = (_REPO_ROOT / "src" / "embedagent" / "harness" / "extension.py").read_text(
        encoding="utf-8"
    )

    assert "session.task_graph" not in source
    assert 'getattr(session, "task_graph"' not in source


def test_query_engine_no_longer_imports_default_harness_extension_directly():
    source = (_REPO_ROOT / "src" / "embedagent" / "query_engine.py").read_text(encoding="utf-8")

    assert "from embedagent.harness.extension import CHarnessWorkflowExtension" not in source
    assert "CHarnessWorkflowExtension(" not in source


def test_snapshot_projector_prefers_generic_workflow_state():
    from embedagent.session_projector import SessionSnapshotProjector
    from embedagent.session_runtime import ManagedSession

    session = Session()
    session.workflow_state["workflow"] = {
        "id": "fake_workflow",
        "label": "Fake Workflow",
        "state": "active",
        "summary": "workflow summary",
        "items": [{"id": "task-1", "content": "workflow task", "status": "in_progress"}],
        "activity": "workflow activity",
        "metadata": {
            "current_phase": "workflow:phase",
            "discipline_profile": "workflow:discipline",
        },
    }
    state = ManagedSession(session=session, current_mode="build")

    snapshot = SessionSnapshotProjector().build_snapshot(state, summary={}, runtime={})

    assert snapshot["workflow"]["id"] == "fake_workflow"
    assert snapshot["current_phase"] == "workflow:phase"
    assert snapshot["discipline_profile"] == "workflow:discipline"
    assert snapshot["current_activity"] == "workflow activity"
    assert snapshot["task_summary"] == "workflow summary"
    assert snapshot["task_items"] == [
        {"id": "task-1", "content": "workflow task", "status": "in_progress"}
    ]


def test_session_snapshot_projector_no_longer_reads_task_graph_directly():
    source = (_REPO_ROOT / "src" / "embedagent" / "session_projector.py").read_text(
        encoding="utf-8"
    )

    assert "task_graph" not in source


def test_inprocess_frontend_task_api_uses_workflow_state_projection():
    source = (_REPO_ROOT / "src" / "embedagent" / "inprocess_adapter.py").read_text(
        encoding="utf-8"
    )
    module = ast.parse(source)
    list_tasks_node = None
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == "list_tasks":
            list_tasks_node = node
            break
    assert list_tasks_node is not None
    names = set()
    attributes = set()
    for node in ast.walk(list_tasks_node):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            attributes.add(node.attr)

    assert "task_graph" not in names
    assert "task_graph" not in attributes


def test_inprocess_frontend_task_api_does_not_import_harness_task_store_directly():
    source = (_REPO_ROOT / "src" / "embedagent" / "inprocess_adapter.py").read_text(
        encoding="utf-8"
    )

    assert "from embedagent.harness import task_store" not in source
    assert "embedagent.harness.task_store" not in source


def test_inprocess_adapter_no_longer_constructs_harness_runner_directly():
    source = (_REPO_ROOT / "src" / "embedagent" / "inprocess_adapter.py").read_text(
        encoding="utf-8"
    )

    assert "from embedagent.harness.runner import HarnessRunner" not in source
    assert "HarnessRunner()" not in source


def test_inprocess_adapter_gets_default_harness_extension_from_factory():
    source = (_REPO_ROOT / "src" / "embedagent" / "inprocess_adapter.py").read_text(
        encoding="utf-8"
    )

    assert "from embedagent.harness.extension import CHarnessWorkflowExtension" not in source
    assert "CHarnessWorkflowExtension(" not in source
    assert "build_default_extension_set" in source


def test_query_engine_tool_activation_does_not_use_runtime_harness_pack_fallback():
    from embedagent.default_extensions import build_default_extension_set
    from embedagent.permissions import PermissionPolicy
    from embedagent.query_engine import QueryEngine

    tools = ToolRuntimeBoundaryProbe()
    default_extensions = build_default_extension_set(tools)
    engine = QueryEngine(
        client=DoneClient(),
        tools=tools,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace="."),
        extension_manager=default_extensions.manager,
    )

    allowed = engine._allowed_tools_for_mode("build", "chat")
    schemas = engine._schemas_for_active_tools("build", "chat")
    names = set(item["function"]["name"] for item in schemas)

    assert "read_file" in allowed
    assert "run_recipe" in allowed
    assert "run_recipe" in names
    assert "propose_mode_switch" not in names


def test_core_pack_no_longer_contains_harness_workflow_tools():
    from embedagent.harness.packs import (
        C_WORKFLOW_BUILD_LITE_PACK,
        C_WORKFLOW_CORE_PACK,
        C_WORKFLOW_DEBUG_LITE_PACK,
        C_WORKFLOW_VERIFY_PACK,
    )

    assert "run_recipe" not in C_WORKFLOW_CORE_PACK
    assert "list_recipes" not in C_WORKFLOW_CORE_PACK
    assert "task_status" not in C_WORKFLOW_CORE_PACK
    assert "run_recipe" in C_WORKFLOW_BUILD_LITE_PACK
    assert "task_status" in C_WORKFLOW_BUILD_LITE_PACK
    assert "run_recipe" in C_WORKFLOW_DEBUG_LITE_PACK
    assert "task_status" in C_WORKFLOW_DEBUG_LITE_PACK
    assert "run_recipe" in C_WORKFLOW_VERIFY_PACK
    assert "task_status" in C_WORKFLOW_VERIFY_PACK


def test_tooling_package_no_longer_reexports_c_workflow_packs():
    import embedagent.tooling as tooling

    assert importlib.util.find_spec("embedagent.tooling.packs") is None
    for name in (
        "BUILD_LITE_PACK",
        "CORE_PACK",
        "DEBUG_LITE_PACK",
        "VERIFY_PACK",
        "PACKS",
        "pack_tool_names",
    ):
        assert not hasattr(tooling, name)


def test_mode_allowed_tools_no_longer_own_harness_workflow_tools():
    from embedagent.modes import allowed_tools_for

    harness_tools = {
        "list_recipes",
        "run_recipe",
        "report_quality_v2",
        "record_failing_evidence",
        "task_status",
    }
    for mode_name in ("explore", "spec", "build", "debug", "verify"):
        leaked = sorted(set(allowed_tools_for(mode_name)) & harness_tools)
        assert leaked == [], "%s leaks harness tools: %s" % (mode_name, leaked)


def test_tool_runtime_default_schemas_follow_mode_contract_not_harness_pack(tmp_path):
    from embedagent.tools import ToolRuntime

    runtime = ToolRuntime(str(tmp_path))

    default_names = set(
        item["function"]["name"] for item in runtime.schemas_for("verify", workflow_state="review")
    )

    assert "read_file" in default_names
    assert "grep_text" in default_names
    assert "run_recipe" not in default_names
    assert "task_status" not in default_names


def test_bare_tool_runtime_does_not_register_default_c_workflow_tools(tmp_path):
    from embedagent.tools import ToolRuntime

    runtime = ToolRuntime(str(tmp_path))
    names = set(item["name"] for item in runtime.catalog_entries())

    assert "read_file" in names
    assert "list_recipes" not in names
    assert "run_recipe" not in names
    assert "task_status" not in names
    assert "report_quality_v2" not in names


def test_default_c_workflow_extension_registers_workflow_tools(tmp_path):
    from embedagent.default_extensions import build_default_extension_set
    from embedagent.extensions import ExtensionContext, ToolRegistrationEvent
    from embedagent.tools import ToolRuntime

    runtime = ToolRuntime(str(tmp_path))
    default_set = build_default_extension_set(runtime)
    default_set.manager.register_tools(
        ToolRegistrationEvent(current_mode="build", workflow_state_name="chat", reason="test"),
        ExtensionContext(workspace=str(tmp_path), tool_registry=runtime),
    )
    names = set(item["name"] for item in runtime.catalog_entries())

    assert "list_recipes" in names
    assert "run_recipe" in names
    assert "task_status" in names
    assert "record_failing_evidence" in names


def test_default_c_workflow_extension_registers_context_reducers(tmp_path):
    from embedagent.context import ContextManager
    from embedagent.default_extensions import build_default_extension_set
    from embedagent.tools import ToolRuntime

    runtime = ToolRuntime(str(tmp_path))
    context_manager = ContextManager()
    default_set = build_default_extension_set(runtime)
    default_set.manager.register_context_reducers(context_manager.reducers)

    reducers = context_manager.reducers
    assert "run_recipe" in reducers._reducers
    assert "report_quality_v2" in reducers._reducers
    assert "task_status" in reducers._reducers
    assert "run_recipe" in reducers.high_priority_tool_names()
    assert "report_quality_v2" in reducers.high_priority_tool_names()


def test_tool_runtime_no_longer_imports_harness_runtime_metadata():
    source = (_REPO_ROOT / "src" / "embedagent" / "tools" / "runtime.py").read_text(
        encoding="utf-8"
    )

    assert "OFFICIAL_HARNESS_TOOL_METADATA" not in source
    assert "embedagent.tools.harness_runtime" not in source


def test_default_c_workflow_tool_metadata_survives_package_registration(tmp_path):
    from embedagent.default_extensions import build_default_extension_set
    from embedagent.extensions import ExtensionContext, ToolRegistrationEvent
    from embedagent.tools import ToolRuntime

    runtime = ToolRuntime(str(tmp_path))
    default_set = build_default_extension_set(runtime)
    default_set.manager.register_tools(
        ToolRegistrationEvent(current_mode="verify", workflow_state_name="chat", reason="test"),
        ExtensionContext(workspace=str(tmp_path), tool_registry=runtime),
    )

    entry = runtime.tool_catalog_entry("run_recipe")
    assert entry["permission_category"] == "toolchain_exec"
    assert entry["source_type"] == "harness"
    assert entry["activity_kind"] == "diagnostic"
    assert entry["interrupt_behavior"] == "cancel"


def test_tool_runtime_no_longer_imports_harness_mode_describer():
    source = (_REPO_ROOT / "src" / "embedagent" / "tools" / "runtime.py").read_text(
        encoding="utf-8"
    )

    assert "OfficialRuntimeModes" not in source
    assert "pack_tool_names" not in source


def test_harness_package_owns_c_workflow_packs():
    from embedagent.harness.packs import C_WORKFLOW_CORE_PACK, pack_tool_names

    assert "run_recipe" not in C_WORKFLOW_CORE_PACK
    assert "run_recipe" in pack_tool_names("build_lite")
    assert "task_status" in pack_tool_names("verify")


def test_importing_tool_runtime_does_not_import_harness_runtime_modules():
    script = (
        "import sys\n"
        "import embedagent.tools.runtime\n"
        "for name in ('embedagent.tools.harness_runtime', 'embedagent.harness.runner'):\n"
        "    print(name, name in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(_REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )

    assert "embedagent.tools.harness_runtime False" in result.stdout
    assert "embedagent.harness.runner False" in result.stdout


def test_tool_runtime_no_longer_exposes_legacy_schema_alias():
    source = (_REPO_ROOT / "src" / "embedagent" / "tools" / "runtime.py").read_text(
        encoding="utf-8"
    )
    legacy_alias = "def " + "schemas_for_" + "mode"

    assert legacy_alias not in source


def test_tool_runtime_no_longer_exposes_allowed_tool_names_alias():
    source = (_REPO_ROOT / "src" / "embedagent" / "tools" / "runtime.py").read_text(
        encoding="utf-8"
    )
    legacy_alias = "def " + "allowed_tool_" + "names"

    assert legacy_alias not in source


def test_frontend_tool_catalog_gets_harness_tools_from_workflow_extension(tmp_path, monkeypatch):
    from embedagent.inprocess_adapter import InProcessAdapter
    from embedagent.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    monkeypatch.setattr(
        "embedagent.inprocess_adapter.allowed_tools_for",
        lambda mode_name: ["read_file", "ask_user"],
    )

    names = set(item.get("name") for item in adapter.get_tool_catalog())

    assert "read_file" in names
    assert "run_recipe" in names
    assert "report_quality_v2" in names
    assert "task_status" in names


def test_c_harness_extension_active_tools_include_verify_foundation():
    from embedagent.harness.extension import CHarnessWorkflowExtension

    names = CHarnessWorkflowExtension().allowed_tool_names("verify")

    assert "run_recipe" in names
    assert "report_quality_v2" in names
    assert "task_status" in names
    assert "bash" in names
    assert "read_file" in names
    assert "grep_text" in names
    assert "write_file" not in names
    assert "edit_file" not in names


def test_c_harness_extension_is_inactive_for_non_harness_modes():
    from embedagent.harness.extension import CHarnessWorkflowExtension

    extension = CHarnessWorkflowExtension()

    assert extension.allowed_tool_names("explore") == set()
    assert extension.allowed_tool_names("spec") == set()


def test_c_harness_package_manifest_does_not_drive_active_tools():
    from embedagent.harness.extension import CHarnessWorkflowExtension

    extension = CHarnessWorkflowExtension()
    manifest = extension.package_manifest()

    assert manifest["package_id"] == "embedagent.c_workflow"
    assert "read_file" in [
        name for pack in manifest["packs"] if pack["name"] == "core" for name in pack["tool_names"]
    ]
    assert extension.allowed_tool_names("explore") == set()
    assert "run_recipe" in extension.allowed_tool_names("build")


def test_inprocess_adapter_tool_catalog_uses_shared_extension_manager(tmp_path):
    from embedagent.inprocess_adapter import InProcessAdapter
    from embedagent.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    adapter.extension_manager.register(CatalogExtension())

    names = set(item.get("name") for item in adapter.get_tool_catalog())

    assert "git_diff" in names


def test_inprocess_adapter_passes_extension_manager_to_query_engine(tmp_path):
    from embedagent.inprocess_adapter import InProcessAdapter
    from embedagent.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    engine = adapter._build_engine()

    assert engine.extension_manager is adapter.extension_manager


def test_inprocess_adapter_session_engine_uses_shared_extension_manager(tmp_path):
    from embedagent.inprocess_adapter import InProcessAdapter
    from embedagent.tools import ToolRuntime

    adapter = InProcessAdapter(client=DoneClient(), tools=ToolRuntime(str(tmp_path)))
    snapshot = adapter.create_session(mode="build")
    session_id = str(snapshot.get("session_id") or "")
    state = adapter._require_session(session_id)

    assert state.engine.extension_manager is adapter.extension_manager


def test_bare_query_engine_uses_empty_extension_host_without_c_harness(tmp_path):
    from embedagent.query_engine import QueryEngine
    from embedagent.tools import ToolRuntime

    engine = QueryEngine(client=DoneClient(), tools=ToolRuntime(str(tmp_path)), max_turns=1)

    assert engine.extension_manager.diagnostics() == []
    assert "run_recipe" not in engine._allowed_tools_for_mode("build", "chat")
    assert "task_status" not in engine._allowed_tools_for_mode("build", "chat")
    assert "propose_mode_switch" not in set(
        item["function"]["name"] for item in engine._schemas_for_active_tools("build", "chat")
    )


def test_query_engine_no_longer_dispatches_extension_manager_hooks_directly():
    source = (_REPO_ROOT / "src" / "embedagent" / "query_engine.py").read_text(encoding="utf-8")
    forbidden = [
        ".should_inject_workflow(",
        ".allowed_tool_names(",
        ".register_tools(",
        ".describe_prompt(",
        ".initialize_workflow_state(",
        ".context(",
        ".before_tool_call(",
        ".after_tool_result(",
        ".handle_tool_call(",
    ]
    for needle in forbidden:
        assert "extension_manager" + needle not in source


def test_inprocess_adapter_no_longer_depends_on_removed_sync_facade(tmp_path):
    from embedagent.inprocess_adapter import InProcessAdapter
    from embedagent.tools import ToolRuntime

    symbol = "Harness" + "State" + "Synchronizer"
    source = (_REPO_ROOT / "src" / "embedagent" / "inprocess_adapter.py").read_text(
        encoding="utf-8"
    )
    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))

    assert symbol not in source
    assert "_harness_sync" not in source
    assert not hasattr(adapter, "_harness_sync")


def test_inprocess_adapter_import_does_not_load_removed_sync_module():
    script = (
        "import sys\n"
        "import embedagent.inprocess_adapter\n"
        "module_name = 'embedagent.services.' + 'harness_' + 'state_' + 'synchronizer'\n"
        "print(module_name in sys.modules)\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(_REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=True,
    )

    assert result.stdout.strip() == "False"


def test_services_no_longer_export_removed_sync_facade():
    import embedagent.services as services

    symbol = "Harness" + "State" + "Synchronizer"

    assert symbol not in getattr(services, "__all__", [])
    assert not hasattr(services, symbol)


def test_removed_sync_facade_module_is_absent():
    module_file = "harness_" + "state_" + "synchronizer.py"
    path = _REPO_ROOT / "src" / "embedagent" / "services" / module_file

    assert not path.exists()
