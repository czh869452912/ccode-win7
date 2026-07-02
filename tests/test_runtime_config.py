from embedagent_core.runtime_config import RuntimeConfigReducer


def _event(event_type, payload, seq=1, event_id="evt-1", ts="2026-06-14T00:00:00Z"):
    return {
        "schema_version": 2,
        "session_id": "sess-runtime-config",
        "event_id": event_id,
        "seq": seq,
        "ts": ts,
        "type": event_type,
        "payload": payload,
    }


def test_runtime_configured_sets_safe_model_profile_and_active_tools():
    events = [
        _event(
            "runtime_configured",
            {
                "reason": "session_start",
                "model_profile": {
                    "name": "local-qwen",
                    "source_type": "configured",
                    "source_id": "llm",
                    "metadata": {"base_url": "http://localhost:11434/v1"},
                    "api_key": "secret-value",
                },
                "active_tool_names": ["write_file", "read_file", "read_file"],
                "registered_tool_names": [
                    "write_file",
                    "read_file",
                    "run_recipe",
                    "read_file",
                ],
                "capability_counts": {"tool": 4, "resource": 1},
            },
        )
    ]

    state = RuntimeConfigReducer().reduce(events)
    payload = state.to_dict()

    assert payload["model_profile"]["name"] == "local-qwen"
    assert payload["model_profile"]["metadata"]["base_url"] == "http://localhost:11434/v1"
    assert "api_key" not in payload["model_profile"]
    assert payload["active_tool_names"] == ["read_file", "write_file"]
    assert payload["registered_tool_names"] == ["read_file", "run_recipe", "write_file"]
    assert payload["capability_counts"] == {"resource": 1, "tool": 4}
    assert payload["last_reason"] == "session_start"


def test_resource_reloaded_advances_revision_but_resource_discovered_does_not():
    discovered = _event(
        "resource_discovered",
        {
            "reason": "scan",
            "counts": {"skills": 1, "prompts": 0, "recipes": 0, "diagnostics": 0},
            "resource_paths": {"skill_paths": [".embedagent/skills"]},
            "diagnostics": [],
        },
        seq=1,
        event_id="evt-discovered",
    )
    reloaded = _event(
        "resource_reloaded",
        {
            "reason": "command",
            "counts": {"skills": 1, "prompts": 1, "recipes": 0, "diagnostics": 0},
            "resource_paths": {"skill_paths": [".embedagent/skills"]},
            "diagnostics": [],
        },
        seq=2,
        event_id="evt-reloaded",
    )

    state = RuntimeConfigReducer().reduce([discovered, reloaded])
    revision = state.to_dict()["resource_revision"]

    assert revision["revision"] == 1
    assert revision["event_id"] == "evt-reloaded"
    assert revision["seq"] == 2
    assert revision["reason"] == "command"
    assert revision["counts"]["skills"] == 1
    assert revision["counts"]["prompts"] == 1
    assert revision["resource_paths"]["skill_paths"] == [".embedagent/skills"]


def test_provider_request_snapshot_records_safe_turn_snapshot_metadata():
    event = _event(
        "operation_started",
        {
            "operation_id": "provider:s-1",
            "kind": "provider_request",
            "metadata": {
                "turn_snapshot": {
                    "snapshot_id": "ts-123",
                    "mode_name": "build",
                    "workflow_state": "chat",
                    "active_tool_names": ["read_file"],
                    "registered_tool_names": ["write_file", "read_file", "read_file"],
                    "model_profile": {"name": "local-qwen"},
                    "capability_counts": {"tool": 3},
                    "resource_revision": {"revision": 2, "event_id": "evt-reload"},
                    "messages": [{"role": "user", "content": "secret prompt"}],
                    "tool_schemas": [{"function": {"name": "read_file"}}],
                }
            },
        },
    )

    state = RuntimeConfigReducer().reduce([event])
    payload = state.to_dict()
    provider = payload["provider_requests"][0]

    assert provider["operation_id"] == "provider:s-1"
    assert provider["snapshot_id"] == "ts-123"
    assert provider["mode_name"] == "build"
    assert provider["active_tool_names"] == ["read_file"]
    assert provider["registered_tool_names"] == ["read_file", "write_file"]
    assert provider["resource_revision"]["revision"] == 2
    assert payload["active_tool_names"] == ["read_file"]
    assert payload["registered_tool_names"] == ["read_file", "write_file"]
    assert payload["model_profile"]["name"] == "local-qwen"
    assert payload["capability_counts"]["tool"] == 3
    assert "messages" not in provider
    assert "tool_schemas" not in provider


def test_provider_request_snapshot_records_safe_prompt_units():
    event = _event(
        "operation_started",
        {
            "operation_id": "provider:s-1",
            "kind": "provider_request",
            "metadata": {
                "turn_snapshot": {
                    "snapshot_id": "ts-123",
                    "prompt_units": [
                        {
                            "kind": "local_skill_listing",
                            "visible_skill_names": ["code-review"],
                            "visible_skill_count": 1,
                            "text": "secret prompt body",
                        }
                    ],
                }
            },
        },
    )

    state = RuntimeConfigReducer().reduce([event])
    provider = state.to_dict()["provider_requests"][0]

    assert provider["prompt_units"] == [
        {
            "kind": "local_skill_listing",
            "visible_skill_names": ["code-review"],
            "visible_skill_count": 1,
        }
    ]
    assert "secret prompt body" not in str(provider)


def test_runtime_config_state_is_json_serializable_when_empty():
    payload = RuntimeConfigReducer().reduce([]).to_dict()

    assert payload["model_profile"] == {}
    assert payload["active_tool_names"] == []
    assert payload["registered_tool_names"] == []
    assert payload["resource_revision"]["revision"] == 0
    assert payload["provider_requests"] == []
