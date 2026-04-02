import os
import shutil
import sys
import unittest
from itertools import count


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.session_restore import SessionRestorer
from embedagent.transcript_store import TranscriptStore


_COUNTER = count(1)


def _make_workspace(name):
    root = os.path.join(
        os.path.dirname(__file__),
        "..",
        "build",
        "test-sandboxes",
        "%s-%s-%s" % (name, os.getpid(), next(_COUNTER)),
    )
    root = os.path.realpath(root)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    return root


class TestSessionRestorer(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("session-restore")
        self.store = TranscriptStore(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_restore_rebuilds_turn_step_and_tool_topology(self):
        session_id = "sess-restore"
        self.store.append_event(session_id, "session_meta", {"current_mode": "code", "started_at": "2026-04-02T00:00:00Z"})
        self.store.append_event(session_id, "message", {"role": "user", "content": "读取文件", "message_id": "m-user", "turn_id": "t-1", "step_id": ""})
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
        self.store.append_event(
            session_id,
            "message",
            {
                "role": "assistant",
                "content": "",
                "message_id": "m-assistant",
                "turn_id": "t-1",
                "step_id": "s-1",
                "actions": [{"name": "read_file", "arguments": {"path": "src/demo.c"}, "call_id": "call-read-1"}],
                "reasoning_content": "先读取文件。",
                "finish_reason": "tool_calls",
            },
        )
        self.store.append_event(
            session_id,
            "tool_call",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "call_id": "call-read-1",
                "tool_name": "read_file",
                "arguments": {"path": "src/demo.c"},
                "status": "started",
            },
        )
        self.store.append_event(
            session_id,
            "tool_result",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "call_id": "call-read-1",
                "tool_name": "read_file",
                "finished_at": "2026-04-02T00:00:01Z",
                "observation": {
                    "success": True,
                    "error": None,
                    "data": {"path": "src/demo.c", "content": "int demo(void) { return 0; }"},
                },
            },
        )
        self.store.append_event(
            session_id,
            "loop_transition",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "reason": "completed",
                "message": "assistant finished",
                "next_mode": "code",
                "turns_used": 1,
                "metadata": {},
            },
        )
        result = SessionRestorer().restore(self.store.load_events(session_id))
        self.assertEqual(result.current_mode, "code")
        self.assertEqual(len(result.session.turns), 1)
        self.assertEqual(result.session.turns[0].turn_id, "t-1")
        self.assertEqual(result.session.turns[0].steps[0].step_id, "s-1")
        self.assertEqual(result.session.turns[0].steps[0].tool_calls[0].call_id, "call-read-1")

    def test_restore_preserves_pending_interaction(self):
        session_id = "sess-pending"
        self.store.append_event(session_id, "session_meta", {"current_mode": "spec"})
        self.store.append_event(session_id, "message", {"role": "user", "content": "继续", "message_id": "m-user", "turn_id": "t-1", "step_id": ""})
        self.store.append_event(
            session_id,
            "pending_interaction",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "kind": "user_input",
                "tool_name": "ask_user",
                "interaction_id": "pi-1",
                "request_payload": {"question": "下一步怎么做？"},
            },
        )
        self.store.append_event(
            session_id,
            "loop_transition",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "reason": "user_input_wait",
                "message": "下一步怎么做？",
                "next_mode": "spec",
                "turns_used": 1,
                "metadata": {},
            },
        )
        result = SessionRestorer().restore(self.store.load_events(session_id))
        self.assertIsNotNone(result.session.pending_interaction)
        self.assertEqual(result.session.pending_interaction.kind, "user_input")
        self.assertEqual(result.session.turns[-1].pending_interaction.interaction_id, "pi-1")

    def test_restore_ignores_damaged_tail_event(self):
        session_id = "sess-tail"
        self.store.append_event(session_id, "session_meta", {"current_mode": "code"})
        path = self.store.resolve_transcript_path(session_id)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("{oops")
        result = SessionRestorer().restore(self.store.load_events(session_id))
        self.assertEqual(result.current_mode, "code")
        self.assertEqual(result.session.session_id, session_id)


if __name__ == "__main__":
    unittest.main()
