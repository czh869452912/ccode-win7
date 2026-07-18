from embedagent_core.session import Observation
from embedagent_host.runtime.review_command import ReviewCommandService


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


def test_review_service_classifies_recipe_evidence_by_payload_shape_not_tool_name():
    service = ReviewCommandService(FakeTools(diff_file_count=0))
    events = [
        {
            "event": "tool_finished",
            "payload": {
                "tool_name": "custom_verify_runner",
                "success": False,
                "call_id": "custom-test",
                "data": {
                    "recipe_action": "test",
                    "test_summary": {"failed": 1},
                },
            },
        }
    ]

    review = service.build_payload(events)

    assert review["verify_evidence_present"] is True
    assert review["tests_seen"] is True
    assert [item["id"] for item in review["findings"]] == ["tests-failed-custom-test"]


def test_review_service_builds_payload_from_session_history_projection():
    service = ReviewCommandService(FakeTools(diff_file_count=0))
    history = {
        "activities": [
            {
                "kind": "tool",
                "tool_name": "run_recipe",
                "call_id": "call-test",
                "status": "error",
                "error": "recipe failed",
                "data": {
                    "recipe_id": "cmake.test.default",
                    "recipe_action": "test",
                    "test_summary": {"failed": 2},
                },
            }
        ]
    }

    review = service.build_payload_from_history(history, limit=400)

    assert review["tests_seen"] is True
    assert [item["id"] for item in review["findings"]] == ["tests-failed-call-test"]
