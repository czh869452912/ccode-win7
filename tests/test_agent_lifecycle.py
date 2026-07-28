import contextlib
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_core.agent_kernel import AgentKernel
from embedagent_core.agent_lifecycle import AgentLifecycleJournal
from embedagent_core.session import LoopTransition, PendingInteraction, Session
from embedagent_core.session_journal import EventIntent


class TestAgentLifecycleJournal(unittest.TestCase):
    def test_records_transition_savepoint_events(self):
        session = Session(session_id="sess-life")
        session.add_user_message("hello", turn_id="turn-1")
        session.begin_step(step_id="step-1")
        events = []
        journal = AgentLifecycleJournal(
            append_event=lambda session, event_type, payload, schema_version=2: events.append(
                {
                    "session_id": session.session_id,
                    "type": event_type,
                    "payload": payload,
                    "schema_version": schema_version,
                }
            ),
            session_guard=lambda: contextlib.nullcontext(),
        )

        journal.record_transition(
            session,
            LoopTransition(reason="completed", message="done", turns_used=1),
        )

        self.assertEqual(
            [item["type"] for item in events],
            [
                "operation_started",
                "loop_transition",
                "operation_finished",
                "operation_finished",
            ],
        )
        self.assertEqual(events[0]["payload"]["kind"], "save_point")
        self.assertEqual(events[1]["payload"]["reason"], "completed")
        self.assertEqual(events[2]["payload"]["kind"], "save_point")
        self.assertEqual(events[3]["payload"]["kind"], "agent_step")
        self.assertEqual(session.turns[-1].transitions[-1].reason, "completed")

    def test_records_pending_transition_lifecycle_events(self):
        session = Session(session_id="sess-pending")
        session.add_user_message("need input", turn_id="turn-1")
        session.begin_step(step_id="step-1")
        pending = PendingInteraction(
            interaction_id="pi-1",
            kind="user_input",
            tool_name="ask_user",
            request_payload={
                "request": {
                    "tool_name": "ask_user",
                    "question": "continue?",
                    "details": {},
                }
            },
        )
        events = []
        journal = AgentLifecycleJournal(
            append_event=lambda session, event_type, payload, schema_version=2: events.append(
                {
                    "type": event_type,
                    "payload": payload,
                    "schema_version": schema_version,
                }
            ),
            session_guard=lambda: contextlib.nullcontext(),
        )

        journal.record_transition(
            session,
            LoopTransition(
                reason="user_input_wait",
                message="continue?",
                pending_interaction=pending,
                next_mode="spec",
            ),
        )

        self.assertEqual(
            [item["type"] for item in events],
            [
                "operation_started",
                "operation_started",
                "loop_transition",
                "operation_finished",
                "operation_finished",
            ],
        )
        self.assertEqual(events[0]["payload"]["kind"], "pending_interaction")
        self.assertEqual(events[0]["payload"]["operation_id"], "pending:pi-1")
        self.assertEqual(events[1]["payload"]["kind"], "save_point")
        self.assertIsNone(session.pending_interaction)
        self.assertEqual(events[-1]["payload"]["kind"], "agent_step")

    def test_finishes_pending_interaction(self):
        session = Session(session_id="sess-finish-pending")
        session.add_user_message("need input", turn_id="turn-1")
        session.begin_step(step_id="step-1")
        pending = PendingInteraction(
            interaction_id="pi-1",
            kind="permission",
            tool_name="write_file",
        )
        events = []
        journal = AgentLifecycleJournal(
            append_event=lambda session, event_type, payload, schema_version=2: events.append(
                {
                    "type": event_type,
                    "payload": payload,
                    "schema_version": schema_version,
                }
            ),
            session_guard=lambda: contextlib.nullcontext(),
        )

        journal.emit_pending_finished(session, pending, "turn-1", "step-1", "resolved")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "operation_finished")
        self.assertEqual(events[0]["payload"]["operation_id"], "pending:pi-1")
        self.assertEqual(events[0]["payload"]["kind"], "pending_interaction")
        self.assertEqual(events[0]["payload"]["result"]["resolution_status"], "resolved")

    def test_persists_workflow_patch_intent_through_injected_committer(self):
        session = Session(session_id="sess-workflow-patch")
        session.add_user_message("run tool", turn_id="turn-1")
        session.begin_step(step_id="step-1")
        events = []
        committed = []
        journal = AgentLifecycleJournal(
            append_event=lambda session, event_type, payload, schema_version=2: events.append(
                {
                    "type": event_type,
                    "payload": payload,
                    "schema_version": schema_version,
                }
            ),
            session_guard=lambda: contextlib.nullcontext(),
        )
        intent = EventIntent(
            "workflow_patch",
            {
                "turn_id": "turn-1",
                "step_id": "step-1",
                "tool_call_id": "call-task",
                "mode_name": "build",
                "workflow_state_name": "chat",
                "workflow": {"summary": "updated"},
                "metadata": {"source": "test-extension"},
            },
        )

        journal.persist_workflow_patch_intent(
            session,
            intent,
            lambda committed_session, committed_intent: committed.append(
                (committed_session, committed_intent)
            ),
        )

        self.assertEqual(
            [item["type"] for item in events],
            ["operation_started", "operation_finished"],
        )
        self.assertEqual(len(committed), 1)
        self.assertIs(committed[0][0], session)
        self.assertIs(committed[0][1], intent)
        self.assertEqual(events[1]["payload"]["kind"], "workflow_patch")
        self.assertEqual(events[1]["payload"]["result"]["workflow"]["summary"], "updated")
        self.assertEqual(session.workflow_state, {})

    def test_kernel_turn_frame_records_finish_and_interrupt(self):
        session = Session(session_id="sess-kernel")
        events = []
        journal = AgentLifecycleJournal(
            append_event=lambda session, event_type, payload, schema_version=2: events.append(
                {
                    "type": event_type,
                    "payload": payload,
                    "schema_version": schema_version,
                }
            ),
            session_guard=lambda: contextlib.nullcontext(),
        )
        kernel = AgentKernel(lifecycle=journal)

        frame = kernel.begin_turn(
            session,
            turn_id="turn-1",
            current_mode="build",
            workflow_state="chat",
            source="user",
        )
        frame.finish(LoopTransition(reason="completed", message="done", turns_used=1))
        interrupted = kernel.begin_turn(
            session,
            turn_id="turn-2",
            current_mode="debug",
            workflow_state="chat",
            source="resume",
        )
        interrupted.interrupt("resume_error", error="boom")

        self.assertEqual(
            [item["type"] for item in events],
            [
                "operation_started",
                "operation_finished",
                "operation_started",
                "operation_interrupted",
            ],
        )
        self.assertEqual(events[0]["payload"]["operation_id"], "turn:turn-1")
        self.assertEqual(events[0]["payload"]["metadata"]["source"], "user")
        self.assertEqual(events[1]["payload"]["result"]["transition_reason"], "completed")
        self.assertEqual(events[2]["payload"]["metadata"]["source"], "resume")
        self.assertEqual(events[3]["payload"]["reason"], "resume_error")
        self.assertEqual(events[3]["payload"]["result"]["error"], "boom")


if __name__ == "__main__":
    unittest.main()
