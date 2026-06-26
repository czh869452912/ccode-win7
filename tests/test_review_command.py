from embedagent.review_command import ReviewCommandService
from embedagent.session import Action, Observation, Session


class FakeTools(object):
    def __init__(self, diff_file_count=0):
        self.diff_file_count = diff_file_count
        self.calls = []

    def execute(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        return Observation(
            tool_name=name,
            success=True,
            error="",
            data={
                "file_count": self.diff_file_count,
                "line_count": 3,
                "diff": "diff --git a/main.c b/main.c",
                "diff_char_count": 29,
            },
        )


def test_review_service_reports_missing_verify_for_dirty_diff():
    tools = FakeTools(diff_file_count=2)
    service = ReviewCommandService(tools)

    review = service.build_payload([])

    assert tools.calls == [("git_diff", {"path": ".", "scope": "working"})]
    assert review["diff_file_count"] == 2
    assert review["verify_evidence_present"] is False
    assert [item["id"] for item in review["findings"]] == ["verify-missing"]


def test_review_service_marks_failing_test_and_renders_markdown():
    service = ReviewCommandService(FakeTools(diff_file_count=0))
    events = [
        {
            "event": "tool_finished",
            "payload": {
                "tool_name": "run_recipe",
                "success": False,
                "call_id": "call-test",
                "data": {
                    "recipe_action": "test",
                    "test_summary": {"failed": 3},
                },
            },
        }
    ]

    review = service.build_payload(events)
    lines = service.markdown_lines(review)

    assert review["verify_evidence_present"] is True
    assert review["tests_seen"] is True
    assert [item["id"] for item in review["findings"]] == ["tests-failed-call-test"]
    assert any("Tests failing" in line for line in lines)


def test_review_service_builds_payload_from_session_tool_observations():
    service = ReviewCommandService(FakeTools(diff_file_count=0))
    session = Session(session_id="sess-review")
    session.add_user_message("verify failed", turn_id="turn-review")
    session.begin_step(step_id="step-review")
    action = Action("run_recipe", {"recipe_id": "cmake.test.default"}, "call-test")
    session.record_tool_call(action)
    session.add_observation(
        action,
        Observation(
            "run_recipe",
            False,
            "recipe failed",
            {
                "recipe_id": "cmake.test.default",
                "recipe_action": "test",
                "test_summary": {"failed": 2},
            },
        ),
    )

    review = service.build_payload_from_session(session, limit=400)

    assert review["tests_seen"] is True
    assert [item["id"] for item in review["findings"]] == ["tests-failed-call-test"]
