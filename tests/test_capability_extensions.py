from embedagent.extensions import (
    ExtensionContext,
    ExtensionManager,
    ResourcesDiscoverResult,
    WorkflowEvent,
)


class BrokenProjectExtension(object):
    extension_id = "broken_project"
    builtin_extension = False

    def context(self, event, context):
        del event, context
        raise RuntimeError("project hook failed")


class BrokenBuiltinExtension(object):
    extension_id = "broken_builtin"
    builtin_extension = True

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


class ResourceExtension(object):
    extension_id = "resources"
    builtin_extension = False

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
