import json


def _assert_no_secret(value, secret):
    assert secret not in json.dumps(value, sort_keys=True)


def test_failed_tool_event_drops_raw_error_text():
    from embedagent_host.runtime.session_event_protocol import SessionEventEncoder

    secret = "provider-token-secret"
    event = SessionEventEncoder().encode(
        "session-1",
        "tool_finished",
        {
            "tool_name": "bash",
            "success": False,
            "error": secret,
            "data": {"error_kind": "provider", "retryable": True},
        },
    )

    assert "error" not in event.payload
    assert event.payload["failure"]["message"] != secret
    _assert_no_secret(event.to_dict(), secret)


def test_project_extension_load_failure_uses_structured_safe_failure(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "broken"
    root.mkdir(parents=True)
    secret = "private-source-fragment"
    (root / "extension.json").write_text(
        '{"id": "broken_extension", "enabled": true, "permissions": ["read"]}',
        encoding="utf-8",
    )
    (root / "extension.py").write_text(
        "raise RuntimeError(%r)" % secret,
        encoding="utf-8",
    )

    from embedagent_host.runtime.project_extensions import load_project_extensions

    payload = load_project_extensions(str(tmp_path))

    diagnostic = payload["diagnostics"][0]
    assert "error" not in diagnostic
    assert diagnostic["failure"]["code"] == "extension_error"
    _assert_no_secret(payload, secret)


def test_extension_manager_diagnostic_is_safe():
    from embedagent_core.extensions import ExtensionManager

    secret = "extension-secret"
    manager = ExtensionManager()
    manager.record_diagnostic("sample", "load", secret)

    diagnostic = manager.diagnostics()[0]
    assert "error" not in diagnostic
    assert diagnostic["message"] != secret
    _assert_no_secret(diagnostic, secret)


def test_session_snapshot_projects_last_failure_without_last_error():
    from embedagent_host.runtime.session_projector import SessionSnapshotProjector
    from embedagent_host.runtime.session_runtime import ManagedSession

    state = ManagedSession(session_id="session-1", current_mode="build")
    state.last_failure = {
        "code": "runtime_error",
        "message": "The operation failed.",
        "kind": "runtime",
    }

    snapshot = SessionSnapshotProjector().build_snapshot(
        state,
        summary={},
        runtime={},
    )

    assert snapshot["last_failure"]["code"] == "runtime_error"
    assert "last_error" not in snapshot
