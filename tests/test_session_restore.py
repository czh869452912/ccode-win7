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
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
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

    def test_restore_stops_at_tool_result_without_prior_tool_call(self):
        session_id = "sess-invalid-tool-result"
        self.store.append_event(session_id, "session_meta", {"current_mode": "code"})
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "读取文件", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
        )
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
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
        self.assertEqual(len(result.session.turns), 1)
        self.assertEqual(len(result.session.turns[0].steps), 1)
        self.assertEqual(result.session.turns[0].steps[0].tool_calls, [])
        self.assertEqual(result.session.turns[0].observations, [])
        self.assertEqual(result.session.turns[0].transitions, [])

    def test_restore_stops_at_pending_resolution_without_pending_interaction(self):
        session_id = "sess-invalid-resolution"
        self.store.append_event(session_id, "session_meta", {"current_mode": "spec"})
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "继续", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
        )
        self.store.append_event(
            session_id,
            "pending_resolution",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "interaction_id": "pi-1",
                "kind": "user_input",
                "tool_name": "ask_user",
                "resolution_payload": {"answer": "继续"},
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
                "next_mode": "spec",
                "turns_used": 1,
                "metadata": {},
            },
        )
        result = SessionRestorer().restore(self.store.load_events(session_id))
        self.assertEqual(len(result.session.turns), 1)
        self.assertIsNone(result.session.pending_interaction)
        self.assertEqual(result.session.turns[0].pending_interaction, None)
        self.assertEqual(result.session.turns[0].transitions, [])

    def test_restore_stops_at_step_started_without_user_turn(self):
        session_id = "sess-invalid-step"
        self.store.append_event(session_id, "session_meta", {"current_mode": "code"})
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
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
        self.assertEqual(result.session.turns, [])

    def test_restore_stops_at_tool_call_without_active_step(self):
        session_id = "sess-invalid-tool-call"
        self.store.append_event(session_id, "session_meta", {"current_mode": "code"})
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "读取文件", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
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
        self.assertEqual(len(result.session.turns), 1)
        self.assertEqual(result.session.turns[0].steps, [])
        self.assertEqual(result.session.turns[0].transitions, [])

    def test_restore_stops_at_tool_call_with_mismatched_step_id(self):
        session_id = "sess-mismatched-tool-call-step"
        self.store.append_event(session_id, "session_meta", {"current_mode": "code"})
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "读取文件", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
        )
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
        self.store.append_event(
            session_id,
            "tool_call",
            {
                "turn_id": "t-1",
                "step_id": "s-999",
                "call_id": "call-read-1",
                "tool_name": "read_file",
                "arguments": {"path": "src/demo.c"},
                "status": "started",
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
        self.assertEqual(len(result.session.turns), 1)
        self.assertEqual(len(result.session.turns[0].steps), 1)
        self.assertEqual(result.session.turns[0].steps[0].step_id, "s-1")
        self.assertEqual(result.session.turns[0].steps[0].tool_calls, [])
        self.assertEqual(result.session.turns[0].transitions, [])

    def test_restore_stops_at_loop_transition_with_mismatched_turn_id(self):
        session_id = "sess-mismatched-transition-turn"
        self.store.append_event(session_id, "session_meta", {"current_mode": "code"})
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "读取文件", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
        )
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
        self.store.append_event(
            session_id,
            "loop_transition",
            {
                "turn_id": "t-other",
                "step_id": "s-1",
                "reason": "completed",
                "message": "assistant finished",
                "next_mode": "code",
                "turns_used": 1,
                "metadata": {},
            },
        )
        result = SessionRestorer().restore(self.store.load_events(session_id))
        self.assertEqual(len(result.session.turns), 1)
        self.assertEqual(result.session.turns[0].turn_id, "t-1")
        self.assertEqual(len(result.session.turns[0].steps), 1)
        self.assertEqual(result.session.turns[0].transitions, [])

    def test_restore_stops_at_compact_boundary_with_missing_preserved_message(self):
        session_id = "sess-invalid-boundary-missing"
        self.store.append_event(session_id, "session_meta", {"current_mode": "code"})
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "读取文件", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
        )
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
        self.store.append_event(
            session_id,
            "message",
            {
                "role": "assistant",
                "content": "已压缩",
                "message_id": "m-assistant",
                "turn_id": "t-1",
                "step_id": "s-1",
                "actions": [],
                "reasoning_content": "",
                "finish_reason": "stop",
            },
        )
        self.store.append_event(
            session_id,
            "compact_boundary",
            {
                "boundary_id": "cb-1",
                "summary_text": "Earlier work summary",
                "compacted_turn_count": 1,
                "created_at": "2026-04-02T00:00:01Z",
                "mode_name": "code",
                "preserved_head_message_id": "m-missing",
                "preserved_tail_message_id": "m-assistant",
                "metadata": {},
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
        self.assertEqual(result.session.compact_boundaries, [])
        self.assertEqual(result.session.turns[0].transitions, [])

    def test_restore_stops_at_compact_boundary_with_reversed_preserved_range(self):
        session_id = "sess-invalid-boundary-order"
        self.store.append_event(session_id, "session_meta", {"current_mode": "code"})
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "读取文件", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
        )
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
        self.store.append_event(
            session_id,
            "message",
            {
                "role": "assistant",
                "content": "first",
                "message_id": "m-assistant-1",
                "turn_id": "t-1",
                "step_id": "s-1",
                "actions": [],
                "reasoning_content": "",
                "finish_reason": "stop",
            },
        )
        self.store.append_event(
            session_id,
            "message",
            {
                "role": "assistant",
                "content": "second",
                "message_id": "m-assistant-2",
                "turn_id": "t-1",
                "step_id": "s-1",
                "actions": [],
                "reasoning_content": "",
                "finish_reason": "stop",
            },
        )
        self.store.append_event(
            session_id,
            "compact_boundary",
            {
                "boundary_id": "cb-1",
                "summary_text": "Earlier work summary",
                "compacted_turn_count": 1,
                "created_at": "2026-04-02T00:00:01Z",
                "mode_name": "code",
                "preserved_head_message_id": "m-assistant-2",
                "preserved_tail_message_id": "m-assistant-1",
                "metadata": {},
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
        self.assertEqual(result.session.compact_boundaries, [])
        self.assertEqual(result.session.turns[0].transitions, [])

    def test_restore_stops_at_assistant_message_with_mismatched_turn_id(self):
        session_id = "sess-invalid-assistant-message"
        self.store.append_event(session_id, "session_meta", {"current_mode": "code"})
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "读取文件", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
        )
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
        self.store.append_event(
            session_id,
            "message",
            {
                "role": "assistant",
                "content": "bad assistant",
                "message_id": "m-assistant",
                "turn_id": "t-other",
                "step_id": "s-1",
                "actions": [],
                "reasoning_content": "",
                "finish_reason": "stop",
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
        self.assertEqual(len(result.session.turns), 1)
        self.assertEqual(result.session.turns[0].assistant_message, "")
        self.assertEqual(result.session.turns[0].transitions, [])

    def test_restore_stops_at_tool_message_with_mismatched_step_id(self):
        session_id = "sess-invalid-tool-message-step"
        self.store.append_event(session_id, "session_meta", {"current_mode": "code"})
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "读取文件", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
        )
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
        self.store.append_event(
            session_id,
            "message",
            {
                "role": "tool",
                "content": "{\"success\": true, \"error\": null, \"data\": {\"path\": \"src/demo.c\"}}",
                "message_id": "m-tool",
                "turn_id": "t-1",
                "step_id": "s-other",
                "tool_call_id": "call-legacy",
                "tool_name": "read_file",
                "kind": "tool_result",
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
        self.assertEqual(len(result.session.turns), 1)
        self.assertEqual([item.role for item in result.session.messages], ["user"])
        self.assertEqual(result.session.turns[0].transitions, [])

    def test_restore_stops_at_duplicate_message_id(self):
        session_id = "sess-duplicate-message-id"
        self.store.append_event(session_id, "session_meta", {"current_mode": "code"})
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "first", "message_id": "m-dup", "turn_id": "t-1", "step_id": ""},
        )
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "second", "message_id": "m-dup", "turn_id": "t-2", "step_id": ""},
        )
        self.store.append_event(
            session_id,
            "loop_transition",
            {
                "turn_id": "t-2",
                "step_id": "",
                "reason": "completed",
                "message": "assistant finished",
                "next_mode": "code",
                "turns_used": 1,
                "metadata": {},
            },
        )
        result = SessionRestorer().restore(self.store.load_events(session_id))
        self.assertEqual(len(result.session.turns), 1)
        self.assertEqual(result.session.turns[0].turn_id, "t-1")
        self.assertEqual(result.session.turns[0].user_message, "first")
        self.assertEqual(result.session.turns[0].transitions, [])

    def test_restore_stops_at_duplicate_tool_call_id(self):
        session_id = "sess-duplicate-call-id"
        self.store.append_event(session_id, "session_meta", {"current_mode": "code"})
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "读取文件", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
        )
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
        self.store.append_event(
            session_id,
            "tool_call",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "call_id": "call-dup",
                "tool_name": "read_file",
                "arguments": {"path": "src/demo.c"},
                "status": "started",
            },
        )
        self.store.append_event(
            session_id,
            "tool_call",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "call_id": "call-dup",
                "tool_name": "search_text",
                "arguments": {"path": ".", "query": "demo"},
                "status": "started",
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
        self.assertEqual(len(result.session.turns), 1)
        self.assertEqual(len(result.session.turns[0].steps), 1)
        self.assertEqual(len(result.session.turns[0].steps[0].tool_calls), 1)
        self.assertEqual(result.session.turns[0].steps[0].tool_calls[0].tool_name, "read_file")
        self.assertEqual(result.session.turns[0].transitions, [])

    def test_restore_stops_at_pending_resolution_with_mismatched_turn_id(self):
        session_id = "sess-resolution-wrong-turn"
        self.store.append_event(session_id, "session_meta", {"current_mode": "spec"})
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "继续", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
        )
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
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
            "pending_resolution",
            {
                "turn_id": "t-other",
                "step_id": "s-1",
                "interaction_id": "pi-1",
                "kind": "user_input",
                "tool_name": "ask_user",
                "resolution_payload": {"answer": "继续"},
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
                "next_mode": "spec",
                "turns_used": 1,
                "metadata": {},
            },
        )
        result = SessionRestorer().restore(self.store.load_events(session_id))
        self.assertIsNotNone(result.session.pending_interaction)
        self.assertEqual(result.session.pending_interaction.interaction_id, "pi-1")
        self.assertEqual(result.session.turns[0].transitions, [])

    def test_restore_stops_at_pending_resolution_with_mismatched_step_id(self):
        session_id = "sess-resolution-wrong-step"
        self.store.append_event(session_id, "session_meta", {"current_mode": "spec"})
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "继续", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
        )
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
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
            "pending_resolution",
            {
                "turn_id": "t-1",
                "step_id": "s-other",
                "interaction_id": "pi-1",
                "kind": "user_input",
                "tool_name": "ask_user",
                "resolution_payload": {"answer": "继续"},
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
                "next_mode": "spec",
                "turns_used": 1,
                "metadata": {},
            },
        )
        result = SessionRestorer().restore(self.store.load_events(session_id))
        self.assertIsNotNone(result.session.pending_interaction)
        self.assertEqual(result.session.pending_interaction.interaction_id, "pi-1")
        self.assertEqual(result.session.turns[0].transitions, [])

    def test_restore_stops_at_pending_resolution_with_mismatched_interaction_id(self):
        session_id = "sess-resolution-wrong-id"
        self.store.append_event(session_id, "session_meta", {"current_mode": "spec"})
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "继续", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
        )
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
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
            "pending_resolution",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "interaction_id": "pi-other",
                "kind": "user_input",
                "tool_name": "ask_user",
                "resolution_payload": {"answer": "继续"},
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
                "next_mode": "spec",
                "turns_used": 1,
                "metadata": {},
            },
        )
        result = SessionRestorer().restore(self.store.load_events(session_id))
        self.assertIsNotNone(result.session.pending_interaction)
        self.assertEqual(result.session.pending_interaction.interaction_id, "pi-1")
        self.assertEqual(result.session.turns[0].transitions, [])

    def test_restore_stops_at_pending_resolution_with_mismatched_tool_name(self):
        session_id = "sess-resolution-wrong-tool"
        self.store.append_event(session_id, "session_meta", {"current_mode": "spec"})
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "继续", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
        )
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
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
            "pending_resolution",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "interaction_id": "pi-1",
                "kind": "user_input",
                "tool_name": "propose_mode_switch",
                "resolution_payload": {"answer": "继续"},
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
                "next_mode": "spec",
                "turns_used": 1,
                "metadata": {},
            },
        )
        result = SessionRestorer().restore(self.store.load_events(session_id))
        self.assertIsNotNone(result.session.pending_interaction)
        self.assertEqual(result.session.pending_interaction.tool_name, "ask_user")
        self.assertEqual(result.session.turns[0].transitions, [])

    def test_restore_stops_at_tool_result_with_mismatched_tool_name(self):
        session_id = "sess-tool-result-wrong-tool"
        self.store.append_event(session_id, "session_meta", {"current_mode": "code"})
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "读取文件", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
        )
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
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
                "tool_name": "search_text",
                "finished_at": "2026-04-02T00:00:01Z",
                "observation": {
                    "success": True,
                    "error": None,
                    "data": {"query": "demo"},
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
        step = result.session.turns[0].steps[0]
        self.assertEqual(len(step.tool_calls), 1)
        self.assertEqual(step.tool_calls[0].tool_name, "read_file")
        self.assertEqual(step.tool_calls[0].status, "started")
        self.assertEqual(result.session.turns[0].observations, [])
        self.assertEqual(result.session.turns[0].transitions, [])

    def test_restore_stops_at_tool_result_with_mismatched_arguments(self):
        session_id = "sess-tool-result-wrong-args"
        self.store.append_event(session_id, "session_meta", {"current_mode": "code"})
        self.store.append_event(
            session_id,
            "message",
            {"role": "user", "content": "读取文件", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
        )
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
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
                "arguments": {"path": "src/other.c"},
                "finished_at": "2026-04-02T00:00:01Z",
                "observation": {
                    "success": True,
                    "error": None,
                    "data": {"path": "src/other.c"},
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
        step = result.session.turns[0].steps[0]
        self.assertEqual(len(step.tool_calls), 1)
        self.assertEqual(step.tool_calls[0].arguments, {"path": "src/demo.c"})
        self.assertEqual(step.tool_calls[0].status, "started")
        self.assertEqual(result.session.turns[0].observations, [])
        self.assertEqual(result.session.turns[0].transitions, [])


if __name__ == "__main__":
    unittest.main()
