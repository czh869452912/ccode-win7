from embedagent.extensions import (
    ContextPatch,
    ExtensionCapability,
    ExtensionContext,
    ExtensionManager,
    ResourcesDiscoverResult,
    ToolCallDecision,
    ToolRegistrationEvent,
    ToolResultPatch,
    WorkflowEvent,
)
from embedagent.session import Action, AssistantReply, Observation


def _capabilities_for(extension, *hook_names):
    return [
        ExtensionCapability(hook_name, getattr(extension, hook_name)) for hook_name in hook_names
    ]


class ExplicitContextExtension(object):
    extension_id = "explicit_context"
    builtin_extension = False

    def extension_capabilities(self):
        return [
            ExtensionCapability(
                event_type="extension.context",
                hook_name="context",
                handler=self._context,
            )
        ]

    def _context(self, event, context):
        assert event.current_mode == "build"
        assert context.workspace == "."
        return ContextPatch(messages=[{"role": "system", "content": "explicit context"}])


class LegacyOnlyContextExtension(object):
    extension_id = "legacy_only_context"
    builtin_extension = False

    def context(self, event, context):
        del event, context
        raise AssertionError("method-name extension hooks must not be auto-registered")


class InvalidCapabilityRecordExtension(object):
    extension_id = "invalid_capability"
    builtin_extension = False

    def extension_capabilities(self):
        return [{"hook_name": "context"}]


def test_extension_manager_registers_explicit_capability_records_only():
    manager = ExtensionManager([ExplicitContextExtension(), LegacyOnlyContextExtension()])

    patch = manager.context(
        WorkflowEvent(current_mode="build"),
        ExtensionContext(workspace="."),
    )

    assert patch.messages == [{"role": "system", "content": "explicit context"}]
    assert manager.diagnostics() == []


def test_extension_manager_records_invalid_capability_records():
    manager = ExtensionManager([InvalidCapabilityRecordExtension()])

    patch = manager.context(WorkflowEvent(current_mode="build"), ExtensionContext(workspace="."))

    assert patch.messages == []
    diagnostics = manager.diagnostics()
    assert len(diagnostics) == 1
    assert diagnostics[0]["extension_id"] == "invalid_capability"
    assert diagnostics[0]["event"] == "extension_capabilities"
    assert "invalid capability record" in diagnostics[0]["error"]


def test_agent_event_bus_reduces_in_source_order():
    from embedagent.agent_event_bus import AgentEvent, AgentEventBus

    bus = AgentEventBus()
    calls = []

    def first(event, context):
        calls.append((event.event_type, context["workspace"], "first"))
        return {"source": "first"}

    def second(event, context):
        calls.append((event.event_type, context["workspace"], "second"))
        return {"source": "second"}

    bus.register_reducer("extension.context", "builtin_context", "builtin", first)
    bus.register_reducer("extension.context", "project_context", "project", second)

    result = bus.dispatch(
        AgentEvent(
            event_type="extension.context",
            payload={"mode": "build"},
            metadata={"reason": "test"},
        ),
        {"workspace": "."},
    )

    assert calls == [
        ("extension.context", ".", "first"),
        ("extension.context", ".", "second"),
    ]
    assert [item["source_id"] for item in result.reducer_results] == [
        "builtin_context",
        "project_context",
    ]
    assert [item["value"]["source"] for item in result.reducer_results] == [
        "first",
        "second",
    ]
    assert result.diagnostics == []


def test_agent_event_bus_records_project_reducer_diagnostics():
    from embedagent.agent_event_bus import AgentEvent, AgentEventBus

    bus = AgentEventBus()

    def broken(event, context):
        del event, context
        raise RuntimeError("project reducer failed")

    bus.register_reducer("extension.context", "broken_project", "project", broken)

    result = bus.dispatch(AgentEvent(event_type="extension.context"))

    assert result.reducer_results == []
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0]["source_id"] == "broken_project"
    assert result.diagnostics[0]["source_type"] == "project"
    assert result.diagnostics[0]["event_type"] == "extension.context"
    assert result.diagnostics[0]["error"] == "project reducer failed"


def test_agent_event_bus_observers_run_before_reducers_without_results():
    from embedagent.agent_event_bus import AgentEvent, AgentEventBus

    bus = AgentEventBus()
    calls = []

    def observer(event, context):
        del event, context
        calls.append("observer")
        return {"ignored": True}

    def reducer(event, context):
        del event, context
        calls.append("reducer")
        return {"kept": True}

    bus.register_reducer("extension.context", "context_reducer", "project", reducer)
    bus.register_observer("extension.context", "context_observer", "project", observer)

    result = bus.dispatch(AgentEvent(event_type="extension.context"))

    assert calls == ["observer", "reducer"]
    assert result.observer_results == []
    assert [item["value"] for item in result.reducer_results] == [{"kept": True}]


class BrokenProjectExtension(object):
    extension_id = "broken_project"
    builtin_extension = False

    def extension_capabilities(self):
        return _capabilities_for(self, "context")

    def context(self, event, context):
        del event, context
        raise RuntimeError("project hook failed")


class BrokenBuiltinExtension(object):
    extension_id = "broken_builtin"
    builtin_extension = True

    def extension_capabilities(self):
        return _capabilities_for(self, "context")

    def context(self, event, context):
        del event, context
        raise RuntimeError("builtin hook failed")


def test_project_extension_hook_error_is_recorded_and_isolated():
    manager = ExtensionManager([BrokenProjectExtension()])

    patch = manager.context(
        WorkflowEvent(current_mode="build"),
        ExtensionContext(workspace="."),
    )

    diagnostics = manager.diagnostics()
    assert patch.messages == []
    assert len(diagnostics) == 1
    assert diagnostics[0]["extension_id"] == "broken_project"
    assert diagnostics[0]["event"] == "context"
    assert diagnostics[0]["error"] == "project hook failed"
    assert diagnostics[0]["severity"] == "error"
    assert diagnostics[0]["metadata"]["agent_event_type"] == "extension.context"
    assert diagnostics[0]["metadata"]["handler_kind"] == "reducer"


def test_builtin_extension_hook_error_is_recorded_and_raised():
    manager = ExtensionManager([BrokenBuiltinExtension()])

    try:
        manager.context(
            WorkflowEvent(current_mode="build"),
            ExtensionContext(workspace="."),
        )
    except RuntimeError as exc:
        assert str(exc) == "builtin hook failed"
    else:
        raise AssertionError("built-in extension error should fail closed")

    diagnostics = manager.diagnostics()
    assert len(diagnostics) == 1
    assert diagnostics[0]["extension_id"] == "broken_builtin"
    assert diagnostics[0]["event"] == "context"
    assert diagnostics[0]["metadata"]["agent_event_type"] == "extension.context"


class ResourceExtension(object):
    extension_id = "resources"
    builtin_extension = False

    def extension_capabilities(self):
        return _capabilities_for(self, "resources_discover")

    def resources_discover(self, event, context):
        assert event.cwd == "."
        assert event.reason == "startup"
        assert context.workspace == "."
        return ResourcesDiscoverResult(
            skill_paths=[".embedagent/skills", ".embedagent/skills"],
            prompt_paths=[".embedagent/prompts"],
            recipe_paths=[".embedagent/recipes"],
            metadata={"source": "resource-extension"},
        )


def test_resources_discover_merges_and_deduplicates_paths():
    manager = ExtensionManager([ResourceExtension()])

    result = manager.discover_resources(".", reason="startup")

    assert result.skill_paths == [".embedagent/skills"]
    assert result.prompt_paths == [".embedagent/prompts"]
    assert result.recipe_paths == [".embedagent/recipes"]
    assert result.metadata == {"source": "resource-extension"}


class BrokenResourceExtension(object):
    extension_id = "broken_resources"
    builtin_extension = False

    def extension_capabilities(self):
        return _capabilities_for(self, "resources_discover")

    def resources_discover(self, event, context):
        del event, context
        raise RuntimeError("resource hook failed")


def test_resources_discover_error_records_bus_metadata():
    manager = ExtensionManager([BrokenResourceExtension()])

    result = manager.discover_resources(".", reason="reload")

    diagnostics = manager.diagnostics()
    assert result.skill_paths == []
    assert len(diagnostics) == 1
    assert diagnostics[0]["extension_id"] == "broken_resources"
    assert diagnostics[0]["event"] == "resources_discover"
    assert diagnostics[0]["metadata"]["agent_event_type"] == "extension.resources_discover"
    assert diagnostics[0]["metadata"]["handler_kind"] == "reducer"


class CapturingClient(object):
    def __init__(self):
        self.messages = []

    def generate(self, messages, tools=None):
        from embedagent.session import AssistantReply

        del tools
        self.messages = list(messages)
        return AssistantReply(content="done", actions=[], finish_reason="stop")

    def stream(
        self,
        messages,
        tools=None,
        on_text_delta=None,
        on_reasoning_delta=None,
    ):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None:
            on_text_delta(reply.content)
        if on_reasoning_delta is not None:
            on_reasoning_delta(reply.reasoning_content)
        return reply


class ContextInjectingExtension(object):
    extension_id = "context_injector"
    builtin_extension = False

    def extension_capabilities(self):
        return _capabilities_for(self, "context")

    def context(self, event, context):
        from embedagent.extensions import ContextPatch

        assert event.current_mode == "build"
        assert context.workspace
        messages = list(event.messages)
        messages.append({"role": "system", "content": "extension context note"})
        return ContextPatch(messages=messages, metadata={"changed": True})


def test_query_engine_applies_extension_context_patch(tmp_path):
    from embedagent.permissions import PermissionPolicy
    from embedagent.query_engine import QueryEngine
    from embedagent.tools import ToolRuntime

    client = CapturingClient()
    tools = ToolRuntime(str(tmp_path))
    manager = ExtensionManager([ContextInjectingExtension()])
    engine = QueryEngine(
        client=client,
        tools=tools,
        permission_policy=PermissionPolicy(
            auto_approve_all=True,
            workspace=str(tmp_path),
        ),
        extension_manager=manager,
    )

    engine.submit_user_turn(
        user_text="read context",
        stream=False,
        initial_mode="build",
    )

    assert {"role": "system", "content": "extension context note"} in client.messages


class ToolPolicyExtension(object):
    extension_id = "tool_policy"
    builtin_extension = False

    def extension_capabilities(self):
        return _capabilities_for(self, "tool_call", "tool_result")

    def tool_call(self, event, context):
        del context
        if event.tool_name == "blocked_tool":
            return ToolCallDecision(block=True, reason="blocked by extension")
        updated = dict(event.tool_arguments)
        updated["path"] = "redirected.txt"
        return ToolCallDecision(
            updated_arguments=updated,
            metadata={"rewritten": True},
        )

    def tool_result(self, event, context):
        del context
        return ToolResultPatch(
            observation=Observation(
                tool_name=event.tool_name,
                success=True,
                error=None,
                data={"patched": True},
            )
        )


def test_tool_call_hook_blocks_or_rewrites_arguments():
    manager = ExtensionManager([ToolPolicyExtension()])

    blocked = manager.before_tool_call(
        WorkflowEvent(tool_name="blocked_tool", tool_arguments={}),
        ExtensionContext(workspace="."),
    )
    rewritten = manager.before_tool_call(
        WorkflowEvent(
            tool_name="read_file",
            tool_arguments={"path": "original.txt"},
        ),
        ExtensionContext(workspace="."),
    )

    assert blocked.block is True
    assert blocked.reason == "blocked by extension"
    assert rewritten.updated_arguments == {"path": "redirected.txt"}
    assert rewritten.metadata == {"rewritten": True}


class FirstRewriteToolExtension(object):
    extension_id = "first_rewrite"
    builtin_extension = False

    def extension_capabilities(self):
        return _capabilities_for(self, "tool_call")

    def tool_call(self, event, context):
        del context
        updated = dict(event.tool_arguments)
        updated["path"] = "first.txt"
        return ToolCallDecision(updated_arguments=updated, metadata={"first": True})


class SecondRewriteThenBlockToolExtension(object):
    extension_id = "second_rewrite"
    builtin_extension = False

    def extension_capabilities(self):
        return _capabilities_for(self, "tool_call")

    def tool_call(self, event, context):
        del context
        assert event.tool_arguments["path"] == "first.txt"
        updated = dict(event.tool_arguments)
        updated["path"] = "second.txt"
        return ToolCallDecision(updated_arguments=updated, metadata={"second": True})


class BlockingAfterRewriteToolExtension(object):
    extension_id = "block_after_rewrite"
    builtin_extension = False

    def extension_capabilities(self):
        return _capabilities_for(self, "tool_call")

    def tool_call(self, event, context):
        del context
        assert event.tool_arguments["path"] == "second.txt"
        return ToolCallDecision(
            block=True,
            reason="blocked after rewrite",
            metadata={"blocked": True},
        )


class ShouldNotRunToolExtension(object):
    extension_id = "should_not_run"
    builtin_extension = False

    def extension_capabilities(self):
        return _capabilities_for(self, "tool_call")

    def tool_call(self, event, context):
        del event, context
        raise AssertionError("first blocking tool decision must stop the chain")


def test_tool_call_hook_preserves_sequential_rewrites_and_first_block_wins():
    event = WorkflowEvent(tool_name="read_file", tool_arguments={"path": "original.txt"})
    manager = ExtensionManager(
        [
            FirstRewriteToolExtension(),
            SecondRewriteThenBlockToolExtension(),
            BlockingAfterRewriteToolExtension(),
            ShouldNotRunToolExtension(),
        ]
    )

    decision = manager.before_tool_call(event, ExtensionContext(workspace="."))

    assert decision.block is True
    assert decision.reason == "blocked after rewrite"
    assert decision.updated_arguments == {"path": "second.txt"}
    assert decision.metadata == {"first": True, "second": True, "blocked": True}
    assert event.tool_arguments == {"path": "second.txt"}


class BrokenToolCallExtension(object):
    extension_id = "broken_tool_call"
    builtin_extension = False

    def extension_capabilities(self):
        return _capabilities_for(self, "tool_call")

    def tool_call(self, event, context):
        del event, context
        raise RuntimeError("tool call reducer failed")


def test_tool_call_hook_error_records_bus_metadata():
    manager = ExtensionManager([BrokenToolCallExtension()])

    decision = manager.before_tool_call(
        WorkflowEvent(tool_name="read_file", tool_arguments={"path": "a.txt"}),
        ExtensionContext(workspace="."),
    )

    diagnostics = manager.diagnostics()
    assert decision.block is False
    assert len(diagnostics) == 1
    assert diagnostics[0]["extension_id"] == "broken_tool_call"
    assert diagnostics[0]["event"] == "tool_call"
    assert diagnostics[0]["metadata"]["agent_event_type"] == "extension.tool_call"
    assert diagnostics[0]["metadata"]["handler_kind"] == "reducer"


def test_tool_result_hook_can_replace_observation():
    manager = ExtensionManager([ToolPolicyExtension()])

    patch = manager.after_tool_result(
        WorkflowEvent(
            tool_name="read_file",
            observation=Observation("read_file", True, None, {"original": True}),
        ),
        ExtensionContext(workspace="."),
    )

    assert patch.observation.success is True
    assert patch.observation.data == {"patched": True}


class BrokenToolResultExtension(object):
    extension_id = "broken_tool_result"
    builtin_extension = False

    def extension_capabilities(self):
        return _capabilities_for(self, "tool_result")

    def tool_result(self, event, context):
        del event, context
        raise RuntimeError("tool result reducer failed")


def test_tool_result_hook_error_records_bus_metadata():
    manager = ExtensionManager([BrokenToolResultExtension()])

    patch = manager.after_tool_result(
        WorkflowEvent(
            tool_name="read_file",
            observation=Observation("read_file", True, None, {"original": True}),
        ),
        ExtensionContext(workspace="."),
    )

    diagnostics = manager.diagnostics()
    assert patch.observation is None
    assert len(diagnostics) == 1
    assert diagnostics[0]["extension_id"] == "broken_tool_result"
    assert diagnostics[0]["event"] == "tool_result"
    assert diagnostics[0]["metadata"]["agent_event_type"] == "extension.tool_result"
    assert diagnostics[0]["metadata"]["handler_kind"] == "reducer"


class BrokenRegisterToolsExtension(object):
    extension_id = "broken_register_tools"
    builtin_extension = False

    def extension_capabilities(self):
        return _capabilities_for(self, "register_tools")

    def register_tools(self, event, context):
        del event, context
        raise RuntimeError("register tools hook failed")


def test_register_tools_hook_error_records_bus_metadata(tmp_path):
    from embedagent.tools import ToolRuntime

    manager = ExtensionManager([BrokenRegisterToolsExtension()])

    manager.register_tools(
        ToolRegistrationEvent(
            current_mode="build",
            workflow_state_name="chat",
            reason="test",
        ),
        ExtensionContext(workspace=str(tmp_path), tool_registry=ToolRuntime(str(tmp_path))),
    )

    diagnostics = manager.diagnostics()
    assert len(diagnostics) == 1
    assert diagnostics[0]["extension_id"] == "broken_register_tools"
    assert diagnostics[0]["event"] == "register_tools"
    assert diagnostics[0]["metadata"]["agent_event_type"] == "extension.register_tools"
    assert diagnostics[0]["metadata"]["handler_kind"] == "reducer"


class ToolCallingClient(object):
    def __init__(self, action):
        self.action = action

    def generate(self, messages, tools=None):
        del messages, tools
        return AssistantReply(
            content="using tool",
            actions=[self.action],
            finish_reason="tool_calls",
        )

    def stream(
        self,
        messages,
        tools=None,
        on_text_delta=None,
        on_reasoning_delta=None,
    ):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None:
            on_text_delta(reply.content)
        if on_reasoning_delta is not None:
            on_reasoning_delta(reply.reasoning_content)
        return reply


class BlockingToolExtension(object):
    extension_id = "blocking_tool"
    builtin_extension = False

    def extension_capabilities(self):
        return _capabilities_for(self, "tool_call")

    def tool_call(self, event, context):
        del context
        if event.tool_name == "read_file":
            return ToolCallDecision(block=True, reason="blocked by extension")
        return None


class PatchingToolResultExtension(object):
    extension_id = "patching_tool_result"
    builtin_extension = False

    def extension_capabilities(self):
        return _capabilities_for(self, "tool_result")

    def tool_result(self, event, context):
        del context
        return ToolResultPatch(
            observation=Observation(
                event.tool_name,
                True,
                None,
                {"patched_by_extension": True},
            )
        )


def test_query_engine_tool_call_hook_can_block_tool_execution(tmp_path):
    from embedagent.permissions import PermissionPolicy
    from embedagent.query_engine import QueryEngine
    from embedagent.tools import ToolRuntime

    target = tmp_path / "blocked.txt"
    target.write_text("blocked", encoding="utf-8")
    action = Action("read_file", {"path": "blocked.txt"}, "call-read")
    engine = QueryEngine(
        client=ToolCallingClient(action),
        tools=ToolRuntime(str(tmp_path)),
        permission_policy=PermissionPolicy(
            auto_approve_all=True,
            workspace=str(tmp_path),
        ),
        extension_manager=ExtensionManager([BlockingToolExtension()]),
        max_turns=1,
    )

    result = engine.submit_user_turn("read file", stream=False, initial_mode="build")
    observation = result.session.turns[-1].observations[-1]

    assert observation.success is False
    assert observation.error == "blocked by extension"
    assert observation.data["error_kind"] == "extension_blocked"


def test_query_engine_tool_result_hook_can_replace_observation(tmp_path):
    from embedagent.permissions import PermissionPolicy
    from embedagent.query_engine import QueryEngine
    from embedagent.tools import ToolRuntime

    target = tmp_path / "readme.txt"
    target.write_text("hello", encoding="utf-8")
    action = Action("read_file", {"path": "readme.txt"}, "call-read")
    engine = QueryEngine(
        client=ToolCallingClient(action),
        tools=ToolRuntime(str(tmp_path)),
        permission_policy=PermissionPolicy(
            auto_approve_all=True,
            workspace=str(tmp_path),
        ),
        extension_manager=ExtensionManager([PatchingToolResultExtension()]),
        max_turns=1,
    )

    result = engine.submit_user_turn("read file", stream=False, initial_mode="build")
    observation = result.session.turns[-1].observations[-1]

    assert observation.success is True
    assert observation.data == {"patched_by_extension": True}


def test_agent_extension_host_applies_context_and_tool_result_workflow_patch(tmp_path):
    from embedagent.agent_extension_host import AgentExtensionHost
    from embedagent.extensions import ContextPatch, WorkflowPatch
    from embedagent.permissions import PermissionPolicy
    from embedagent.session import ContextAssemblyResult, Session
    from embedagent.tools import ToolRuntime

    class ContextAndPatchExtension(object):
        extension_id = "context_and_patch"
        builtin_extension = False

        def extension_capabilities(self):
            return _capabilities_for(self, "context", "tool_result")

        def context(self, event, context):
            del context
            messages = list(event.messages)
            messages.append({"role": "system", "content": "extension context"})
            return ContextPatch(messages=messages)

        def tool_result(self, event, context):
            del context
            return ToolResultPatch(
                workflow_patch=WorkflowPatch(
                    workflow={"task_summary": {"total": 1}},
                    metadata={"source": "test"},
                )
            )

    session = Session()
    runtime = ToolRuntime(str(tmp_path))
    host = AgentExtensionHost(
        manager=ExtensionManager([ContextAndPatchExtension()]),
        tools=runtime,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path)),
    )
    assembly = ContextAssemblyResult(
        messages=[{"role": "user", "content": "hello"}],
        used_chars=0,
        approx_tokens=0,
        compacted=False,
        summarized_turns=0,
        recent_turns=0,
        policy=None,
        budget=None,
        stats={},
    )

    patched = host.apply_context_patch(session, "build", "chat", assembly, force_compact=False)
    observation = host.apply_tool_result_patch(
        session,
        Action("read_file", {"path": "a.txt"}, "call-read"),
        "build",
        "chat",
        Observation("read_file", True, None, {"content": "ok"}),
    )

    assert patched.messages[-1]["content"] == "extension context"
    assert observation.success is True
    assert session.workflow_state["workflow"]["task_summary"]["total"] == 1
    assert session.workflow_state["extensions"]["last_workflow_patch"]["source"] == "test"


def test_session_snapshot_projects_extension_state_and_diagnostics():
    from embedagent.session import Session
    from embedagent.session_projector import SessionSnapshotProjector
    from embedagent.session_runtime import ManagedSession

    session = Session()
    session.workflow_state["extensions"] = {
        "sample": {"state": {"enabled": True}},
    }
    state = ManagedSession(session=session, current_mode="build")

    snapshot = SessionSnapshotProjector().build_snapshot(
        state,
        summary={},
        runtime={},
        extension_diagnostics=[
            {
                "extension_id": "sample",
                "event": "context",
                "error": "sample error",
                "severity": "error",
                "source": "project",
                "metadata": {},
            }
        ],
    )

    assert snapshot["extensions"] == {"sample": {"state": {"enabled": True}}}
    assert snapshot["extension_diagnostics"][0]["extension_id"] == "sample"
    assert snapshot["extension_diagnostics"][0]["error"] == "sample error"


class SnapshotBrokenExtension(object):
    extension_id = "snapshot_broken"
    builtin_extension = False

    def extension_capabilities(self):
        return _capabilities_for(self, "context")

    def context(self, event, context):
        del event, context
        raise RuntimeError("snapshot diagnostic")


def test_inprocess_snapshot_includes_extension_diagnostics(tmp_path):
    from embedagent.inprocess_adapter import InProcessAdapter
    from embedagent.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    adapter.extension_manager = ExtensionManager([SnapshotBrokenExtension()])
    adapter.extension_manager.context(
        WorkflowEvent(current_mode="build"),
        ExtensionContext(workspace=str(tmp_path)),
    )
    snapshot = adapter.create_session(mode="build")

    diagnostics = snapshot.get("extension_diagnostics") or []
    assert diagnostics
    assert diagnostics[0]["extension_id"] == "snapshot_broken"
    assert diagnostics[0]["error"] == "snapshot diagnostic"
