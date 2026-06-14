import json

from embedagent.turn_snapshot import TurnSnapshotBuilder


def test_turn_snapshot_builder_copies_provider_inputs_and_sorts_active_tools():
    messages = [{"role": "user", "content": "hello", "nested": {"x": 1}}]
    tool_schemas = [{"type": "function", "function": {"name": "write_file"}}]
    capabilities = {"counts": {"tool": 1}, "descriptors": []}

    snapshot = TurnSnapshotBuilder().build(
        session_id="sess-1",
        turn_id="turn-1",
        step_id="step-1",
        mode_name="build",
        workflow_state="chat",
        messages=messages,
        tool_schemas=tool_schemas,
        active_tool_names=["write_file", "read_file", "read_file"],
        model_profile={"name": "local-qwen"},
        runtime_environment={"python": "3.8"},
        capabilities=capabilities,
        context_stats={"approx_tokens": 42},
    )

    messages[0]["nested"]["x"] = 99
    tool_schemas[0]["function"]["name"] = "mutated"
    capabilities["counts"]["tool"] = 99

    assert snapshot.snapshot_id.startswith("ts-")
    assert snapshot.messages[0]["nested"]["x"] == 1
    assert snapshot.tool_schemas[0]["function"]["name"] == "write_file"
    assert snapshot.active_tool_names == ["read_file", "write_file"]
    assert snapshot.capabilities["counts"]["tool"] == 1
    assert snapshot.context_stats["approx_tokens"] == 42


def test_turn_snapshot_to_dict_is_json_serializable_and_provider_safe():
    snapshot = TurnSnapshotBuilder().build(
        session_id="sess-1",
        turn_id="turn-1",
        step_id="step-1",
        mode_name="verify",
        workflow_state="review",
        messages=[{"role": "system", "content": "safe"}],
        tool_schemas=[],
        active_tool_names=[],
        model_profile={"name": "default-model"},
        runtime_environment={},
        capabilities={"counts": {}, "descriptors": []},
        context_stats={},
    )

    payload = snapshot.to_dict()
    json.dumps(payload, sort_keys=True)

    assert payload["session_id"] == "sess-1"
    assert payload["mode_name"] == "verify"
    assert payload["workflow_state"] == "review"
    assert payload["messages"] == [{"role": "system", "content": "safe"}]
    assert payload["tool_schemas"] == []
    assert payload["model_profile"] == {"name": "default-model"}
