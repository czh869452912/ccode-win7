import os
import shutil
import sys
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_core.api import ApplicationRuntimePolicy, RuntimeDefinition
from embedagent_core.session import (
    Action,
    AssistantReply,
    Observation,
    Session,
)
from embedagent_core.session_journal import SessionJournal
from embedagent_core.session_reducer import SessionReducer
from embedagent_core.session_transaction import SessionRecoveryRequired, SessionTransaction
from embedagent_host.runtime.session_history import SessionHistoryAssembler
from embedagent_host.runtime.transcript_store import TranscriptStore
from session_journal_test_helpers import restore_trusted_events

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


class TestSessionIntegration(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("session-integration")
        self.store = TranscriptStore(self.workspace)
        self.assembler = SessionHistoryAssembler()

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _append_planned_tool_call(self, session_id):
        self.store.append_event(session_id, "session_meta", {"current_mode": "build"})
        self.store.append_event(
            session_id,
            "user",
            {
                "role": "user",
                "content": "Write a file",
                "message_id": "m-user",
                "turn_id": "t-1",
            },
        )
        self.store.append_event(
            session_id,
            "step_started",
            {"turn_id": "t-1", "step_id": "s-1", "step_index": 1},
        )
        self.store.append_event(
            session_id,
            "tool_call",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "call_id": "provider-call",
                "tool_name": "write_file",
                "arguments": {"path": "output.txt", "content": "done"},
            },
        )

    def _restore_transaction(self, session_id):
        transaction = SessionTransaction(
            session_log=self.store,
            journal=SessionJournal(self.store, SessionReducer()),
            loop=None,
            definition=RuntimeDefinition(
                application_policy=ApplicationRuntimePolicy(default_mode="build")
            ),
            projection=None,
            dispatcher=None,
            event_committer=None,
        )
        return transaction._restore_or_create(session_id)

    def _build_schema_v2_transcript(self, session_id="sess-e2e"):
        """Build a realistic schema v2 transcript with multiple turns."""
        # Session meta
        self.store.append_event(
            session_id,
            "session_meta",
            {"current_mode": "build", "started_at": "2026-04-02T00:00:00Z"},
            schema_version=2,
        )

        # Turn 1: User asks, assistant reads file
        self.store.append_event(
            session_id,
            "user",
            {"role": "user", "content": "Read main.c", "message_id": "m-1", "turn_id": "t-1"},
            schema_version=2,
        )
        self.store.append_event(
            session_id,
            "step_started",
            {"turn_id": "t-1", "step_id": "s-1", "step_index": 1},
            schema_version=2,
        )
        self.store.append_event(
            session_id,
            "assistant",
            {
                "role": "assistant",
                "content": "I'll read the file.",
                "message_id": "m-2",
                "parent_message_id": "m-1",
                "turn_id": "t-1",
                "step_id": "s-1",
                "actions": [
                    {"name": "read_file", "arguments": {"path": "main.c"}, "call_id": "call-1"}
                ],
            },
            schema_version=2,
        )
        self.store.append_event(
            session_id,
            "tool_use",
            {
                "role": "tool_use",
                "tool_name": "read_file",
                "call_id": "call-1",
                "arguments": {"path": "main.c"},
                "message_id": "m-3",
                "parent_message_id": "m-2",
                "turn_id": "t-1",
                "step_id": "s-1",
            },
            schema_version=2,
        )
        self.store.append_event(
            session_id,
            "tool_result",
            {
                "role": "tool_result",
                "tool_name": "read_file",
                "call_id": "call-1",
                "observation": {"success": True, "data": "int main() {}", "error": None},
                "message_id": "m-4",
                "parent_message_id": "m-2",
                "turn_id": "t-1",
                "step_id": "s-1",
            },
            schema_version=2,
        )

        # Turn 2: User asks to edit
        self.store.append_event(
            session_id,
            "user",
            {
                "role": "user",
                "content": "Add a comment",
                "message_id": "m-5",
                "parent_message_id": "m-4",
                "turn_id": "t-2",
            },
            schema_version=2,
        )

        return session_id

    def test_schema_v2_write_and_load_roundtrip(self):
        session_id = self._build_schema_v2_transcript()
        events = self.store.load_events(session_id)

        # All events should be normalized to v2 on load
        self.assertTrue(len(events) >= 5)
        for event in events:
            self.assertEqual(event.get("schema_version"), 2)
            self.assertIn("type", event)

        # Check parent chain
        user_event = [e for e in events if e.get("type") == "user"][0]
        assistant_event = [e for e in events if e.get("type") == "assistant"][0]
        self.assertEqual(
            assistant_event.get("parent_message_id"), user_event["payload"]["message_id"]
        )

    def test_restore_does_not_treat_planned_tool_call_as_incomplete_side_effect(self):
        session_id = "sess-planned-tool"
        self._append_planned_tool_call(session_id)

        restored = self._restore_transaction(session_id)

        record = restored.session.turns[-1].steps[-1].tool_calls[0]
        self.assertEqual(record.call_id, "provider-call")

    def test_restore_rejects_unfinished_stable_tool_operation(self):
        session_id = "sess-started-tool"
        self._append_planned_tool_call(session_id)
        self.store.append_event(
            session_id,
            "operation_started",
            {
                "operation_id": "tool:m-assistant-t-1-s-1-1:0",
                "kind": "tool_call",
                "turn_id": "t-1",
                "step_id": "s-1",
                "tool_call_id": "provider-call",
                "metadata": {"tool_name": "write_file"},
            },
        )

        with self.assertRaisesRegex(SessionRecoveryRequired, "incomplete_side_effect") as captured:
            self._restore_transaction(session_id)

        self.assertEqual(captured.exception.stop_reason, "incomplete_side_effect")

    def test_restore_from_schema_v2_events(self):
        session_id = self._build_schema_v2_transcript()
        events = self.store.load_events(session_id)

        result = restore_trusted_events(events)

        self.assertIsNotNone(result.session)
        self.assertEqual(result.transcript_event_count, len(events))
        self.assertEqual(result.consumed_event_count, len(events))
        self.assertEqual(result.skipped_count, 0)
        self.assertTrue(len(result.session.turns) >= 2)

    def test_activity_history_from_restored_session(self):
        session_id = self._build_schema_v2_transcript()
        events = self.store.load_events(session_id)
        result = restore_trusted_events(events)

        history = self.assembler.build(
            result.session,
            "restored",
            "healthy",
            consumed_event_count=result.consumed_event_count,
            transcript_event_count=result.transcript_event_count,
        )

        self.assertIn("activities", history)
        self.assertNotIn("items", history)
        self.assertTrue(len(history["activities"]) >= 4)

        kinds = [item["kind"] for item in history["activities"]]
        self.assertIn("user", kinds)
        self.assertIn("assistant", kinds)
        self.assertIn("tool", kinds)

    def test_full_pipeline_best_effort_with_corruption(self):
        session_id = self._build_schema_v2_transcript()

        # Corrupt the transcript by appending a bad event
        path = self.store.resolve_transcript_path(session_id)
        with open(path, "a", encoding="utf-8") as f:
            bad_event = '{"schema_version": 2, "seq": 999, "type": "user", "parent_message_id": "nonexistent"}'
            f.write(bad_event + "\n")

        # Load events (scan stops at bad event due to seq gap)
        events = self.store.load_events(session_id)

        # Restore with best_effort
        result = restore_trusted_events(events)

        # Should have processed valid events, skipped bad one if it loaded
        self.assertTrue(result.consumed_event_count >= 5)
        self.assertIsNotNone(result.session)

    def test_parent_chain_validation_on_real_transcript(self):
        session_id = self._build_schema_v2_transcript()

        validation = self.store.validate_transcript_chain(session_id)
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["breaks"], [])

    def test_transcript_chain_detects_break(self):
        session_id = "sess-broken"
        self.store.append_event(
            session_id,
            "user",
            {"role": "user", "content": "first", "message_id": "m-1", "turn_id": "t-1"},
            schema_version=2,
        )
        self.store.append_event(
            session_id,
            "user",
            {
                "role": "user",
                "content": "second",
                "message_id": "m-2",
                "parent_message_id": "nonexistent",
                "turn_id": "t-2",
            },
            schema_version=2,
        )

        validation = self.store.validate_transcript_chain(session_id)
        self.assertFalse(validation["valid"])
        self.assertEqual(len(validation["breaks"]), 1)
        self.assertIn("parent_not_found", validation["breaks"][0]["reason"])

    def test_multiple_tool_calls_in_one_step(self):
        session = Session(session_id="sess-multi")
        turn = session.add_user_message("Run multiple tools")
        step = session.begin_step(reasoning="parallel tools")

        # Add assistant reply with 2 tool calls
        reply = AssistantReply(
            content="",
            actions=[
                Action(name="read_file", arguments={"path": "a.c"}, call_id="c1"),
                Action(name="read_file", arguments={"path": "b.c"}, call_id="c2"),
            ],
        )
        session.add_assistant_reply(reply, turn_id=turn.turn_id, step_id=step.step_id)

        # Add observations
        session.add_observation(
            Action(name="read_file", arguments={"path": "a.c"}, call_id="c1"),
            Observation(tool_name="read_file", success=True, error=None, data="content a"),
            turn_id=turn.turn_id,
            step_id=step.step_id,
        )
        session.add_observation(
            Action(name="read_file", arguments={"path": "b.c"}, call_id="c2"),
            Observation(tool_name="read_file", success=True, error=None, data="content b"),
            turn_id=turn.turn_id,
            step_id=step.step_id,
        )

        history = self.assembler.build(session, "live", "healthy")
        tool_activities = [i for i in history["activities"] if i["kind"] == "tool"]

        self.assertEqual(len(tool_activities), 2)
        self.assertEqual([item["call_id"] for item in tool_activities], ["c1", "c2"])
        self.assertEqual([item["status"] for item in tool_activities], ["success", "success"])
        self.assertEqual([item["data"] for item in tool_activities], ["content a", "content b"])


if __name__ == "__main__":
    unittest.main()
