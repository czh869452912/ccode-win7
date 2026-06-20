import json
import unittest

from embedagent.compacted_history import CompactedHistoryReducer


class TestCompactedHistoryReducer(unittest.TestCase):
    def test_reducer_projects_latest_valid_checkpoint(self):
        events = [
            {
                "schema_version": 2,
                "session_id": "sess-compact",
                "event_id": "evt-1",
                "seq": 11,
                "ts": "2026-06-20T00:00:00Z",
                "type": "compacted_history",
                "payload": {
                    "checkpoint_id": "ch-1",
                    "boundary_id": "cb-1",
                    "summary_text": "Earlier work summary",
                    "first_kept_message_id": "m-kept",
                    "replacement_messages": [
                        {
                            "role": "system",
                            "content": "Earlier work summary",
                            "kind": "compacted_history_summary",
                            "metadata": {"checkpoint_id": "ch-1", "boundary_id": "cb-1"},
                        }
                    ],
                    "trigger": "reactive_retry",
                    "phase": "provider_retry",
                    "token_counts": {"approx_before": 1800, "approx_after": 500},
                    "message_counts": {
                        "before": 12,
                        "after": 4,
                        "summarized_turns": 4,
                        "recent_turns": 2,
                    },
                    "file_activity": {
                        "read_files": ["src/demo.c", "src/demo.c"],
                        "modified_files": [],
                    },
                    "evidence_refs": ["ref-a", "ref-a"],
                    "extension_summary": False,
                    "created_at": "2026-06-20T00:00:00Z",
                    "metadata": {"pipeline_steps": ["reactive_compact_retry"]},
                },
            }
        ]

        state = CompactedHistoryReducer().reduce(events)
        payload = state.to_dict()

        self.assertEqual(payload["checkpoint_count"], 1)
        self.assertEqual(payload["latest_checkpoint_id"], "ch-1")
        self.assertEqual(payload["status"], "ready")
        latest = payload["latest_checkpoint"]
        self.assertEqual(latest["checkpoint_id"], "ch-1")
        self.assertEqual(latest["boundary_id"], "cb-1")
        self.assertEqual(latest["first_kept_message_id"], "m-kept")
        self.assertEqual(latest["replacement_message_count"], 1)
        self.assertEqual(latest["replacement_messages"][0]["role"], "system")
        self.assertEqual(latest["file_activity"]["read_files"], ["src/demo.c"])
        self.assertEqual(latest["evidence_refs"], ["ref-a"])
        self.assertEqual(payload["diagnostics"], [])
        json.dumps(payload, sort_keys=True)

    def test_reducer_rejects_duplicate_checkpoint_id(self):
        events = [
            {
                "type": "compacted_history",
                "event_id": "evt-1",
                "seq": 1,
                "payload": {
                    "checkpoint_id": "ch-dup",
                    "summary_text": "First",
                    "replacement_messages": [{"role": "system", "content": "First"}],
                },
            },
            {
                "type": "compacted_history",
                "event_id": "evt-2",
                "seq": 2,
                "payload": {
                    "checkpoint_id": "ch-dup",
                    "summary_text": "Second",
                    "replacement_messages": [{"role": "system", "content": "Second"}],
                },
            },
        ]

        payload = CompactedHistoryReducer().reduce(events).to_dict()

        self.assertEqual(payload["checkpoint_count"], 1)
        self.assertEqual(payload["latest_checkpoint"]["summary_text"], "First")
        self.assertEqual(payload["diagnostics"][0]["reason"], "duplicate_checkpoint_id")
        self.assertEqual(payload["diagnostics"][0]["checkpoint_id"], "ch-dup")

    def test_reducer_rejects_empty_replacement_history(self):
        events = [
            {
                "type": "compacted_history",
                "event_id": "evt-empty",
                "seq": 1,
                "payload": {
                    "checkpoint_id": "ch-empty",
                    "summary_text": "No replacement messages",
                    "replacement_messages": [],
                },
            }
        ]

        payload = CompactedHistoryReducer().reduce(events).to_dict()

        self.assertEqual(payload["checkpoint_count"], 0)
        self.assertEqual(payload["status"], "empty")
        self.assertEqual(payload["diagnostics"][0]["reason"], "missing_replacement_messages")
        self.assertEqual(payload["diagnostics"][0]["checkpoint_id"], "ch-empty")

    def test_reducer_filters_unsafe_replacement_roles(self):
        events = [
            {
                "type": "compacted_history",
                "event_id": "evt-tool",
                "seq": 1,
                "payload": {
                    "checkpoint_id": "ch-tool",
                    "summary_text": "Mixed roles",
                    "replacement_messages": [
                        {"role": "tool", "content": "raw tool output"},
                        {"role": "system", "content": "safe summary"},
                    ],
                },
            }
        ]

        latest = CompactedHistoryReducer().reduce(events).to_dict()["latest_checkpoint"]

        self.assertEqual(latest["replacement_message_count"], 1)
        self.assertEqual(latest["replacement_messages"][0]["role"], "system")
        self.assertEqual(latest["replacement_messages"][0]["content"], "safe summary")


if __name__ == "__main__":
    unittest.main()
