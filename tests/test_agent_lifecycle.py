import contextlib
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_core.agent_kernel import AgentKernel
from embedagent_core.agent_lifecycle import AgentLifecycleJournal
from embedagent_core.session import Action, LoopTransition, PendingInteraction, Session


class TestAgentLifecycleJournal(unittest.TestCase):
    def test_records_transition_savepoint_events(self):
        session = Session(session_id="sess-life")
        session.add_user_message("hello", turn_id="turn-1")
        session.begin_step(step_id="step-1")
        events = []
        journal = AgentLifecycleJournal(
            append_event=lambda session, event_type, payload, schema_version=1: events.append(
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
            append_event=lambda session, event_type, payload, schema_version=1: events.append(
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
                "pending_interaction",
                "operation_started",
                "operation_started",
                "loop_transition",
                "operation_finished",
                "operation_finished",
            ],
        )
        self.assertEqual(events[0]["payload"]["interaction_id"], "pi-1")
        self.assertEqual(events[1]["payload"]["kind"], "pending_interaction")
        self.assertEqual(events[1]["payload"]["operation_id"], "pending:pi-1")
        self.assertEqual(events[2]["payload"]["kind"], "save_point")
        self.assertEqual(events[-1]["payload"]["kind"], "agent_step")
        self.assertIs(session.pending_interaction, pending)

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
            append_event=lambda session, event_type, payload, schema_version=1: events.append(
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

    def test_records_workflow_patch_when_action_changes_workflow_state(self):
        session = Session(session_id="sess-workflow-patch")
        session.add_user_message("run tool", turn_id="turn-1")
        session.begin_step(step_id="step-1")
        events = []
        journal = AgentLifecycleJournal(
            append_event=lambda session, event_type, payload, schema_version=1: events.append(
                {
                    "type": event_type,
                    "payload": payload,
                    "schema_version": schema_version,
                }
            ),
            session_guard=lambda: contextlib.nullcontext(),
        )
        before = journal.workflow_patch_snapshot(session)
        session.workflow_state["workflow"] = {"summary": "updated"}
        session.workflow_state["extensions"] = {"last_workflow_patch": {"source": "test-extension"}}

        journal.capture_workflow_patch_if_changed(
            session,
            Action("task_status", {}, "call-task"),
            "build",
            "chat",
            before,
        )

        self.assertEqual(
            [item["type"] for item in events],
            ["operation_started", "workflow_patch", "operation_finished"],
        )
        self.assertEqual(events[1]["schema_version"], 2)
        self.assertEqual(events[1]["payload"]["workflow"]["summary"], "updated")
        self.assertEqual(events[1]["payload"]["metadata"]["source"], "test-extension")
        self.assertEqual(events[2]["payload"]["kind"], "workflow_patch")

    def test_kernel_turn_frame_records_finish_and_interrupt(self):
        session = Session(session_id="sess-kernel")
        events = []
        journal = AgentLifecycleJournal(
            append_event=lambda session, event_type, payload, schema_version=1: events.append(
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
