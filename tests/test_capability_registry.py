import json

from embedagent.capabilities import (
    CapabilityDescriptor,
    CapabilityRegistry,
)


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
