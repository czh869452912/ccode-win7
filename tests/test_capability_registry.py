import json

from embedagent.capabilities import (
    CapabilityDescriptor,
    CapabilityRegistry,
    command_capability_descriptors,
    model_profile_capability_descriptor,
    resource_capability_descriptors,
    runtime_tool_capability_descriptors,
)
from embedagent.slash_commands import SlashCommandRegistry
from embedagent.tools import ToolRuntime


def test_registry_registers_descriptors_and_serializes_snapshot():
    registry = CapabilityRegistry()
    registry.register(
        CapabilityDescriptor(
            name="read_file",
            kind="tool",
            source_type="builtin",
            source_id="embedagent.core",
            metadata={"permission_category": "read"},
            active=True,
        )
    )
    registry.register(
        CapabilityDescriptor(
            name="review",
            kind="command",
            source_type="builtin",
            source_id="slash_commands",
            metadata={"usage": "/review"},
            active=False,
        )
    )

    snapshot = registry.snapshot()
    payload = snapshot.to_dict()

    assert payload["counts"] == {
        "command": 1,
        "model_profile": 0,
        "resource": 0,
        "tool": 1,
    }
    assert payload["active_names_by_kind"]["tool"] == ["read_file"]
    assert payload["active_names_by_kind"]["command"] == []
    assert payload["descriptors"][0]["kind"] == "command"
    assert payload["descriptors"][1]["kind"] == "tool"
    json.dumps(payload, sort_keys=True)


def test_registry_duplicate_key_replaces_descriptor_without_duplicate_row():
    registry = CapabilityRegistry()
    registry.register(
        CapabilityDescriptor(
            name="read_file",
            kind="tool",
            source_type="builtin",
            source_id="embedagent.core",
            metadata={"version": 1},
            active=False,
        )
    )
    registry.register(
        CapabilityDescriptor(
            name="read_file",
            kind="tool",
            source_type="builtin",
            source_id="embedagent.core",
            metadata={"version": 2},
            active=True,
        )
    )

    payload = registry.snapshot().to_dict()

    assert len(payload["descriptors"]) == 1
    assert payload["descriptors"][0]["metadata"]["version"] == 2
    assert payload["descriptors"][0]["active"] is True


def test_registry_filters_by_kind_and_returns_copies():
    registry = CapabilityRegistry()
    registry.register(CapabilityDescriptor(name="read_file", kind="tool"))
    registry.register(CapabilityDescriptor(name="help", kind="command"))

    tools = registry.descriptors(kind="tool")
    tools[0].metadata["mutated"] = True

    assert [item.name for item in tools] == ["read_file"]
    assert "mutated" not in registry.descriptors(kind="tool")[0].metadata


def test_descriptor_normalizes_empty_source_and_metadata():
    descriptor = CapabilityDescriptor(
        name="  read_file  ",
        kind="  tool ",
        source_type="",
        source_id="",
        metadata=None,
        active=True,
    )

    assert descriptor.name == "read_file"
    assert descriptor.kind == "tool"
    assert descriptor.source_type == "runtime"
    assert descriptor.source_id == "runtime"
    assert descriptor.metadata == {}


def test_runtime_tool_capability_descriptors_project_tool_catalog(tmp_path):
    runtime = ToolRuntime(str(tmp_path))

    descriptors = runtime_tool_capability_descriptors(runtime)
    by_name = dict((item.name, item) for item in descriptors)

    assert "read_file" in by_name
    assert by_name["read_file"].kind == "tool"
    assert by_name["read_file"].source_type == "builtin"
    assert by_name["read_file"].source_id == "embedagent.core"
    assert by_name["read_file"].metadata["permission_category"] == "read"


def test_resource_capability_descriptors_project_local_resources(tmp_path):
    skill_dir = tmp_path / ".embedagent" / "skills"
    skill_dir.mkdir(parents=True)
    skill_path = skill_dir / "review.md"
    skill_path.write_text("# Review\n", encoding="utf-8")

    runtime = ToolRuntime(str(tmp_path))
    resources = runtime.reload_resources(reason="test")

    descriptors = resource_capability_descriptors(resources)

    assert [item.name for item in descriptors] == [".embedagent/skills/review.md"]
    assert descriptors[0].kind == "resource"
    assert descriptors[0].source_type == "local_resource"
    assert descriptors[0].source_id == "skill"
    assert descriptors[0].metadata["path"] == ".embedagent/skills/review.md"


def test_command_and_model_profile_descriptors_are_serializable():
    commands = command_capability_descriptors(SlashCommandRegistry())
    model = model_profile_capability_descriptor(
        {
            "model": "local-qwen",
            "base_url": "http://localhost:11434/v1",
            "api_key": "secret-value",
        }
    )
    registry = CapabilityRegistry(commands + [model])
    payload = registry.snapshot().to_dict()

    command_names = [item["name"] for item in payload["descriptors"] if item["kind"] == "command"]
    model_items = [item for item in payload["descriptors"] if item["kind"] == "model_profile"]

    assert "help" in command_names
    assert model_items[0]["name"] == "local-qwen"
    assert model_items[0]["metadata"]["base_url"] == "http://localhost:11434/v1"
    assert "api_key" not in model_items[0]["metadata"]
    json.dumps(payload, sort_keys=True)
