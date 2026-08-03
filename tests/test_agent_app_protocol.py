import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_protocol import (
    AgentApplicationDescriptor,
    AppBootstrap,
    CapabilitySnapshot,
    CommandDescriptor,
    InteractionActivity,
    InteractionDescriptor,
    KeybindingDescriptor,
    ModeDescriptor,
    SessionBootstrap,
    SessionSnapshot,
    SessionStatus,
    ShellDescriptor,
    SurfaceDescriptor,
    ThreadShell,
    TimelineItemDescriptor,
    ToolPresentation,
    WorkflowPackageDescriptor,
)


class AgentAppProtocolTests(unittest.TestCase):
    def test_capability_snapshot_is_json_safe_and_backend_declared(self):
        snapshot = CapabilitySnapshot(
            schema_version=1,
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
                    summary="Switch to build mode",
                    source_type="agent_profile",
                    source_id="python.profile",
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
            agent_application=AgentApplicationDescriptor(
                id="python",
                label="Python Agent",
                profile_id="python.profile",
                workflow_package_ids=["workflow-python"],
                active=True,
            ),
            agent_applications=[
                AgentApplicationDescriptor(
                    id="python",
                    label="Python Agent",
                    profile_id="python.profile",
                    workflow_package_ids=["workflow-python"],
                    active=True,
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

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["agent_application"]["id"], "python")
        self.assertEqual(payload["agent_applications"][0]["profile_id"], "python.profile")
        self.assertEqual(payload["modes"][0]["id"], "python-build")
        self.assertEqual(payload["commands"][0]["summary"], "Switch to build mode")
        self.assertEqual(payload["commands"][0]["source_type"], "agent_profile")
        self.assertEqual(payload["commands"][0]["source_id"], "python.profile")
        self.assertEqual(payload["tools"][0]["label"], "Pytest")
        self.assertNotIn("agentApplication", json.dumps(payload))
        self.assertNotIn("to" + "dos", json.dumps(payload))
        self.assertNotIn("harness", json.dumps(payload).lower())
        json.dumps(payload)

    def test_thread_detail_contains_activities_not_timeline_replay(self):
        detail = SessionBootstrap(
            schema_version=1,
            event_cursor=0,
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
                        "request_kind": "file-change",
                        "tool_name": "edit_file",
                        "summary": "Edit src/parser.py",
                    },
                )
            ],
            capabilities=CapabilitySnapshot(schema_version=1),
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
            schema_version=1,
            app={"name": "EmbedAgent"},
            workspaces=[],
            shell=ShellDescriptor(
                schema_version=1,
                commands=[CommandDescriptor(id="app.open", label="Open", group="app")],
            ),
            diagnostics={"offline": True},
        )

        payload = bootstrap.to_dict()

        self.assertIn("app", payload)
        self.assertNotIn("history", payload)
        self.assertNotIn("snapshot", payload)

    def test_session_bootstrap_uses_one_versioned_snake_case_shape(self):
        payload = SessionBootstrap(
            schema_version=1,
            event_cursor=4,
            thread=ThreadShell(
                id="s-1",
                title="Session",
                archived=False,
                current_mode="build",
                status="idle",
                updated_at="2026-08-03T00:00:00Z",
            ),
            snapshot={"session_id": "s-1", "workflow_state": {}},
            activities=[],
            capabilities=CapabilitySnapshot(schema_version=1),
        ).to_dict()

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["event_cursor"], 4)
        self.assertEqual(payload["thread"]["current_mode"], "build")
        self.assertNotIn("currentMode", json.dumps(payload))

    def test_app_bootstrap_contains_one_versioned_shell_descriptor(self):
        shell = ShellDescriptor(
            schema_version=1,
            commands=[
                CommandDescriptor(
                    id="app.open",
                    label="Open",
                    group="app",
                    dispatch={"kind": "workspace.open"},
                )
            ],
            surfaces=[
                SurfaceDescriptor(
                    id="files",
                    label="Files",
                    placement="secondary",
                    renderer_key="files",
                )
            ],
            keybindings=[
                KeybindingDescriptor(
                    command_id="app.open",
                    keys="mod+o",
                    when={"workspace": "available"},
                )
            ],
            timeline_items=[
                TimelineItemDescriptor(
                    event_kind="turn.started",
                    renderer_key="turn",
                )
            ],
            interactions=[
                InteractionDescriptor(
                    kind="permission",
                    renderer_key="permission",
                )
            ],
        )
        payload = AppBootstrap(
            schema_version=1,
            app={"name": "EmbedAgent"},
            workspaces=[],
            shell=shell,
        ).to_dict()

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["shell"]["schema_version"], 1)
        self.assertEqual(payload["shell"]["surfaces"][0]["renderer_key"], "files")
        self.assertNotIn("rendererKey", json.dumps(payload))

    def test_current_frontend_dtos_reject_invalid_structure(self):
        valid_thread = ThreadShell(
            id="s-1",
            title="Session",
            archived=False,
            current_mode="build",
            status="idle",
            updated_at="2026-08-03T00:00:00Z",
        )
        invalid_factories = (
            lambda: CapabilitySnapshot(schema_version=0),
            lambda: SessionBootstrap(
                schema_version=1,
                event_cursor=-1,
                thread=valid_thread,
                snapshot={},
                activities=[],
                capabilities=CapabilitySnapshot(schema_version=1),
            ),
            lambda: CommandDescriptor(id="", label="Open", group="app"),
            lambda: CommandDescriptor(
                id="app.open",
                label="Open",
                group="app",
                dispatch=[],
            ),
            lambda: SurfaceDescriptor(
                id="files",
                label="Files",
                placement="right",
                renderer_key="files",
            ),
            lambda: SurfaceDescriptor(
                id="files",
                label="Files",
                placement="secondary",
                renderer_key="",
            ),
            lambda: ToolPresentation(name="read_file", label="Read", renderer_key=""),
        )
        for index, factory in enumerate(invalid_factories):
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    factory()

    def test_session_snapshot_preserves_missing_workflow_state(self):
        snapshot = SessionSnapshot(
            session_id="s-1",
            status=SessionStatus.IDLE,
            current_mode="explore",
            created_at="",
            updated_at="",
        )

        self.assertEqual(snapshot.workflow_state, "")


if __name__ == "__main__":
    unittest.main()
