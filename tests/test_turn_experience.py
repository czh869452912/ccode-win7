from embedagent.turn_experience import TurnExperienceReducer


def _event(event_type, payload, seq):
    return {
        "schema_version": 2,
        "event_id": "evt-%s" % seq,
        "seq": seq,
        "ts": "2026-06-29T00:00:%02dZ" % seq,
        "type": event_type,
        "payload": payload,
    }


def _turn_started(turn_id, seq):
    return _event(
        "operation_started",
        {
            "operation_id": "turn:%s" % turn_id,
            "kind": "turn",
            "turn_id": turn_id,
        },
        seq,
    )


def test_turn_experience_projects_blocked_unverified_files_and_next_steps():
    events = [
        _event(
            "tool_result",
            {
                "tool_name": "write_file",
                "observation": {
                    "success": True,
                    "error": None,
                    "data": {"path": "README.md", "created": True},
                },
            },
            1,
        ),
        _event(
            "tool_result",
            {
                "tool_name": "write_file",
                "observation": {
                    "success": True,
                    "error": None,
                    "data": {"path": "src/main.c", "created": True},
                },
            },
            2,
        ),
        _event(
            "loop_transition",
            {
                "reason": "guard_stop",
                "message": "repeated no-progress action",
            },
            3,
        ),
    ]

    payload = TurnExperienceReducer().reduce(events).to_dict()

    assert payload["status"] == "blocked"
    assert payload["blocker"]["reason"] == "guard_stop"
    assert payload["completed"] == [
        {"kind": "file_created", "path": "README.md"},
        {"kind": "file_created", "path": "src/main.c"},
    ]
    assert payload["unverified"] == [
        {"kind": "validation_missing", "message": "Created files have not been validated."}
    ]
    assert payload["next_steps"] == [
        "Review the blocker, then resume the session after changing the action or project state.",
        "Run validation for the changed files.",
    ]


def test_turn_experience_projects_failed_validation_as_next_fix_step():
    events = [
        _event(
            "tool_result",
            {
                "tool_name": "bash",
                "observation": {
                    "success": False,
                    "error": "命令退出码为 1。",
                    "data": {
                        "command": "python tests/test_calcstats.py",
                        "exit_code": 1,
                        "stderr": "FAIL: compilation error",
                        "outcome_class": "diagnostic_failure",
                        "error_kind": "command_failed",
                    },
                },
            },
            1,
        ),
        _event("loop_transition", {"reason": "completed", "message": ""}, 2),
    ]

    payload = TurnExperienceReducer().reduce(events).to_dict()

    assert payload["status"] == "completed"
    assert payload["last_failure"] == {
        "tool_name": "bash",
        "command": "python tests/test_calcstats.py",
        "exit_code": 1,
        "error": "命令退出码为 1。",
    }
    assert payload["unverified"] == [
        {
            "kind": "validation_failed",
            "command": "python tests/test_calcstats.py",
            "exit_code": 1,
        }
    ]
    assert payload["next_steps"] == ["Inspect the failed validation output and fix the project."]


def test_turn_experience_projects_only_latest_turn_window():
    events = [
        _turn_started("turn-old", 1),
        _event(
            "tool_result",
            {
                "turn_id": "turn-old",
                "tool_name": "write_file",
                "observation": {
                    "success": True,
                    "error": None,
                    "data": {"path": "old.c", "created": True},
                },
            },
            2,
        ),
        _event("loop_transition", {"turn_id": "turn-old", "reason": "completed"}, 3),
        _turn_started("turn-new", 4),
        _event(
            "tool_result",
            {
                "turn_id": "turn-new",
                "tool_name": "write_file",
                "observation": {
                    "success": True,
                    "error": None,
                    "data": {"path": "new.c", "created": True},
                },
            },
            5,
        ),
        _event("loop_transition", {"turn_id": "turn-new", "reason": "completed"}, 6),
    ]

    payload = TurnExperienceReducer().reduce(events).to_dict()

    assert payload["completed"] == [{"kind": "file_created", "path": "new.c"}]
    assert payload["critical_files"] == ["new.c"]
