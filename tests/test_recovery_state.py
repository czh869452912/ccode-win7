import json
import unittest

from embedagent.recovery_state import RecoveryStateReducer


class TestRecoveryStateReducer(unittest.TestCase):
    def test_reducer_projects_structured_recovery_marker(self):
        events = [
            {
                "type": "recovery_marker",
                "event_id": "evt-1",
                "seq": 5,
                "ts": "2026-06-14T00:00:00Z",
                "payload": {
                    "marker_id": "rm-1",
                    "created_at": "2026-06-14T00:00:00Z",
                    "reason": "resume",
                    "status": "partial",
                    "current_mode": "build",
                    "trusted_event_count": 8,
                    "transcript_event_count": 10,
                    "stop_reason": "duplicate_compact_boundary_id",
                    "skipped_count": 0,
                    "skip_reasons": [],
                    "operation_summary": {
                        "total_count": 3,
                        "started_count": 0,
                        "finished_count": 2,
                        "interrupted_count": 1,
                    },
                    "compaction_summary": {
                        "boundary_count": 1,
                        "latest_boundary_id": "cb-1",
                    },
                    "runtime_summary": {
                        "active_tool_count": 4,
                        "resource_revision": 2,
                        "model_profile_name": "local-model",
                    },
                    "metadata": {"source": "resume_session"},
                },
            }
        ]

        state = RecoveryStateReducer().reduce(events)
        payload = state.to_dict()

        self.assertEqual(payload["marker_count"], 1)
        self.assertEqual(payload["latest_marker_id"], "rm-1")
        self.assertEqual(payload["latest_marker"]["status"], "partial")
        self.assertEqual(payload["latest_marker"]["trusted_event_count"], 8)
        self.assertEqual(payload["latest_marker"]["operation_summary"]["interrupted_count"], 1)
        self.assertEqual(
            payload["latest_marker"]["compaction_summary"]["latest_boundary_id"], "cb-1"
        )
        self.assertEqual(payload["latest_marker"]["runtime_summary"]["active_tool_count"], 4)
        self.assertEqual(payload["partial_count"], 1)
        self.assertEqual(payload["diagnostics"], [])
        json.dumps(payload, sort_keys=True)

    def test_reducer_deduplicates_marker_id(self):
        events = [
            {
                "type": "recovery_marker",
                "event_id": "evt-1",
                "seq": 1,
                "payload": {"marker_id": "rm-dup", "status": "clean"},
            },
            {
                "type": "recovery_marker",
                "event_id": "evt-2",
                "seq": 2,
                "payload": {"marker_id": "rm-dup", "status": "partial"},
            },
        ]

        payload = RecoveryStateReducer().reduce(events).to_dict()

        self.assertEqual(payload["marker_count"], 1)
        self.assertEqual(payload["latest_marker"]["status"], "clean")
        self.assertEqual(payload["diagnostics"][0]["reason"], "duplicate_marker_id")

    def test_reducer_handles_empty_transcript(self):
        payload = RecoveryStateReducer().reduce([]).to_dict()

        self.assertEqual(payload["marker_count"], 0)
        self.assertEqual(payload["latest_marker_id"], "")
        self.assertEqual(payload["status"], "empty")


if __name__ == "__main__":
    unittest.main()
