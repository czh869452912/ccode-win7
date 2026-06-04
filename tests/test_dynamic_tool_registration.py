from __future__ import annotations

import pytest

from embedagent.session import Observation
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

    entries = [
        item
        for item in runtime.catalog_entries()
        if item.get("name") == "dynamic_echo"
    ]

    assert len(entries) == 1
    assert entries[0]["source_id"] == "test.extension"


def test_builtin_and_harness_tools_have_source_metadata(tmp_path):
    runtime = ToolRuntime(str(tmp_path))

    assert runtime.tool_catalog_entry("read_file")["source_type"] == "builtin"
    assert runtime.tool_catalog_entry("read_file")["source_id"] == "embedagent.core"
    assert runtime.tool_catalog_entry("run_recipe")["source_type"] == "harness"
    assert runtime.tool_catalog_entry("run_recipe")["source_id"] == "embedagent.harness"
