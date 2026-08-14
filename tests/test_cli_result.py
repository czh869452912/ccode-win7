from dataclasses import FrozenInstanceError

import pytest
from embedagent_protocol import FailureRecord


def _failure(code):
    return FailureRecord(code=code, message="failed", retryable=False, source="test")


def test_completed_result_has_exact_stable_projection():
    from embedagent.cli.result import CliResult

    result = CliResult.completed("s1", "ok")
    assert result.to_dict() == {
        "schema_version": 1,
        "session_id": "s1",
        "status": "completed",
        "exit_code": 0,
        "final_text": "ok",
        "outcome": {},
        "failure": None,
    }
    with pytest.raises(FrozenInstanceError):
        result.status = "failed"


@pytest.mark.parametrize(
    "code, expected_status, expected_exit",
    [
        ("interaction_required", "blocked", 2),
        ("permission_denied", "blocked", 2),
        ("usage_error", "failed", 3),
        ("configuration_error", "failed", 3),
        ("provider_error", "failed", 4),
        ("runtime_error", "failed", 4),
        ("protocol_error", "failed", 4),
        ("session_not_found", "failed", 4),
        ("cancelled", "cancelled", 130),
    ],
)
def test_failure_codes_map_to_stable_status_and_exit_code(code, expected_status, expected_exit):
    from embedagent.cli.result import CliResult

    result = CliResult.from_failure("s1", _failure(code))
    assert result.status == expected_status
    assert result.exit_code == expected_exit
    assert result.to_dict()["failure"]["code"] == code


def test_blocked_result_copies_outcome_and_does_not_expose_mutable_state():
    from embedagent.cli.result import CliResult

    outcome = {"kind": "blocked", "details": {"reason": "approval"}}
    result = CliResult.blocked("s1", outcome=outcome, failure=_failure("interaction_required"))
    outcome["details"]["reason"] = "changed"

    assert result.to_dict()["outcome"]["details"]["reason"] == "approval"
    with pytest.raises(TypeError):
        result.outcome["kind"] = "completed"
