import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.protocol import (
    AppBootstrap,
    CapabilitySnapshot,
    CommandDescriptor,
    InteractionActivity,
    ModeDescriptor,
    ThreadDetailSnapshot,
    ThreadShell,
    ToolPresentation,
    WorkflowPackageDescriptor,
)


class AgentAppProtocolTests(unittest.TestCase):
    def test_capability_snapshot_is_json_safe_and_backend_declared(self):
        snapshot = CapabilitySnapshot(
            modes=[
                ModeDescriptor(
                    id="python-build",
                    label="Python Build",
                    description="Implement Python changes",
                    icon_key="hammer",
                    color_token="success",
                    command_id="mode.python-build",
                )
            ],
            commands=[
                CommandDescriptor(
                    id="mode.python-build",
                    label="Python Build",
                    group="mode",
                    dispatch={"kind": "mode.set", "mode": "python-build"},
                )
            ],
            tools=[
                ToolPresentation(
                    name="pytest",
                    label="Pytest",
                    icon_key="test-tube",
                    renderer_key="command",
                    permission_category="command",
                )
            ],
            workflow_packages=[
                WorkflowPackageDescriptor(
                    id="workflow-python",
                    label="Python",
                    active=True,
                    state={"phase": "test"},
                )
            ],
            resources=[],
            model_profiles=[],
            empty_state={
                "scenario_label": "Python workspace",
                "primary": "Choose a local workspace",
                "secondary": "The selected scenario defines tools and modes.",
            },
        )

        payload = snapshot.to_dict()

        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["modes"][0]["id"], "python-build")
        self.assertEqual(payload["tools"][0]["label"], "Pytest")
        self.assertNotIn("to" + "dos", json.dumps(payload))
        self.assertNotIn("harness", json.dumps(payload).lower())
        json.dumps(payload)

    def test_thread_detail_contains_activities_not_timeline_replay(self):
        detail = ThreadDetailSnapshot(
            thread=ThreadShell(
                id="sess-1",
                title="Parser repair",
                archived=False,
                current_mode="python-build",
                status="waiting_permission",
                updated_at="2026-07-02T10:00:00Z",
                pending_interaction=True,
            ),
            snapshot={"session_id": "sess-1", "status": "waiting_permission"},
            activities=[
                InteractionActivity(
                    id="act-1",
                    kind="approval.requested",
                    request_id="perm-1",
                    turn_id="turn-1",
                    created_at="2026-07-02T10:00:00Z",
                    payload={
                        "requestKind": "file-change",
                        "toolName": "edit_file",
                        "summary": "Edit src/parser.py",
                    },
                )
            ],
            capabilities=CapabilitySnapshot(),
            workflow={"package_id": "workflow-python"},
            integrity={"status": "healthy"},
        )

        payload = detail.to_dict()

        self.assertEqual(payload["history"]["activities"][0]["kind"], "approval.requested")
        self.assertNotIn("timeline", payload)
        self.assertNotIn("turns", payload["history"])
        json.dumps(payload)

    def test_app_bootstrap_does_not_include_session_history(self):
        bootstrap = AppBootstrap(
            app={"name": "EmbedAgent"},
            workspaces=[],
            commands=[CommandDescriptor(id="app.open", label="Open", group="app")],
            surfaces=[{"id": "chat", "label": "Chat"}],
            diagnostics={"offline": True},
        )

        payload = bootstrap.to_dict()

        self.assertIn("app", payload)
        self.assertNotIn("history", payload)
        self.assertNotIn("snapshot", payload)


if __name__ == "__main__":
    unittest.main()
