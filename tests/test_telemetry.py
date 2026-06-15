from __future__ import annotations


def test_safe_telemetry_envelope_keeps_operational_fields_and_redacts_sensitive_values():
    from embedagent.telemetry import build_safe_telemetry_envelope

    envelope = build_safe_telemetry_envelope(
        "tool.finished",
        {
            "status": "ok",
            "tool_name": "intranet_fetch",
            "duration_ms": 42,
            "prompt": "full prompt must not leave process",
            "source_text": "int main(void) { return 0; }",
            "api_key": "secret-key",
            "raw_tool_output": "private output",
            "counts": {"files": 3, "bytes": 128},
            "paths": ["src/main.c", "src/lib.c"],
        },
        source_type="extension",
        source_id="enterprise_tools",
    )

    metadata = envelope["metadata"]
    assert envelope["event_type"] == "tool.finished"
    assert envelope["source_type"] == "extension"
    assert envelope["source_id"] == "enterprise_tools"
    assert metadata["status"] == "ok"
    assert metadata["tool_name"] == "intranet_fetch"
    assert metadata["duration_ms"] == 42
    assert metadata["counts"] == {"files": 3, "bytes": 128}
    assert metadata["paths"] == {"type": "list", "count": 2}
    assert metadata["prompt"] == "<redacted>"
    assert metadata["source_text"] == "<redacted>"
    assert metadata["api_key"] == "<redacted>"
    assert metadata["raw_tool_output"] == "<redacted>"


def test_safe_telemetry_envelope_summarizes_nested_metadata_without_raw_payloads():
    from embedagent.telemetry import build_safe_telemetry_envelope

    envelope = build_safe_telemetry_envelope(
        "provider.request",
        {
            "snapshot_id": "snapshot-1",
            "messages": [{"role": "user", "content": "secret prompt"}],
            "diagnostics": [{"reason": "timeout"}, {"reason": "retry"}],
            "permission_payload": {"decision": "allow", "token": "secret"},
        },
    )

    metadata = envelope["metadata"]
    assert metadata["snapshot_id"] == "snapshot-1"
    assert metadata["messages"] == "<redacted>"
    assert metadata["diagnostics"] == {"type": "list", "count": 2}
    assert metadata["permission_payload"] == "<redacted>"
