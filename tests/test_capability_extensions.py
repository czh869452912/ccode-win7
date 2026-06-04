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
