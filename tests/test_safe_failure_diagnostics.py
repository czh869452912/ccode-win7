from __future__ import annotations

from embedagent_protocol import FailureRecord


def test_failure_record_contains_phase_kind_and_correlation_without_exception_text():
    record = FailureRecord.from_exception(
        phase="tool_execution",
        kind="runtime",
        correlation_id="corr-1",
        exception=RuntimeError("secret prompt and token must not escape"),
    )
    payload = record.to_dict()
    assert payload["phase"] == "tool_execution"
    assert payload["kind"] == "runtime"
    assert payload["correlation_id"] == "corr-1"
    assert "secret prompt" not in repr(payload)
    assert payload["exception_type"] == "RuntimeError"


def test_interaction_failure_remains_distinguishable_from_runtime_failure():
    interaction = FailureRecord(
        code="interaction_required",
        kind="interaction",
        phase="interaction",
    )
    runtime = FailureRecord(code="runtime_error", kind="runtime")
    assert interaction.to_dict()["kind"] == "interaction"
    assert runtime.to_dict()["kind"] == "runtime"
    assert interaction.to_dict()["message"] != runtime.to_dict()["message"]
