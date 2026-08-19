from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_runtime_policy_owns_selected_closure_without_composition_import():
    source = _read("src/embedagent/bundle_policy.py")

    assert "embedagent_composition" not in source
    for field in (
        "runtime_capability_ids",
        "runtime_component_ids",
        "asset_ids",
        "gate_ids",
        "project_distribution_ids",
    ):
        assert field in source
        assert '_selected_closure_ids(plan, "%s")' % field in source


def test_public_failure_paths_do_not_serialize_raw_exception_text():
    adapter = _read("packages/embedagent-host/src/embedagent_host/inprocess_adapter.py")
    protocol = _read(
        "packages/embedagent-host/src/embedagent_host/runtime/session_event_protocol.py"
    )
    projector = _read(
        "packages/embedagent-host/src/embedagent_host/runtime/session_projector.py"
    )
    diagnostics = _read("packages/embedagent-core/src/embedagent_core/extensions.py")

    assert 'state.last_error' not in adapter
    assert '"error": str(exc)' not in adapter
    assert 'data.pop("error", None)' in protocol
    assert '"last_failure"' in projector
    assert '"last_error"' not in projector
    assert '"error":' not in diagnostics


def test_host_shutdown_has_one_scope_owner_and_shared_completion_barrier():
    adapter = _read("packages/embedagent-host/src/embedagent_host/inprocess_adapter.py")
    scope = _read("packages/embedagent-core/src/embedagent_core/registration_scope.py")

    assert "RegistrationScope(" in adapter
    assert '"hosted-runtime"' in adapter
    assert "self._shutdown_complete" in adapter
    assert "self._runtime_scope.quiesce()" in adapter
    assert "self._runtime_scope.dispose()" in adapter
    assert "wait_for.wait()" in scope
    assert "owner_id" in scope
