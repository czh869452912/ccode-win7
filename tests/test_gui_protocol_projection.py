import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_host.runtime.session_runtime import ManagedSession

from embedagent.frontend.gui.backend.protocol_payloads import (
    serialize_app_bootstrap,
    serialize_session_bootstrap,
)


class GuiProtocolProjectionTests(unittest.TestCase):
    def test_session_bootstrap_uses_protocol_history_activities_only(self):
        payload = serialize_session_bootstrap(
            {
                "event_cursor": 7,
                "snapshot": {
                    "session_id": "sess-1",
                    "status": "idle",
                    "current_mode": "python",
                    "workflow_state": {"package_id": "workflow-python"},
                },
                "history": {
                    "activities": [{"id": "a1", "kind": "user", "content": "hi"}],
                    "turns": [{"id": "legacy-turn"}],
                },
                "capabilities": {
                    "modes": [{"id": "python", "label": "Python", "command_id": "mode.python"}],
                    "commands": [
                        {
                            "name": "mode.python",
                            "usage": "Python",
                            "source_type": "mode",
                            "active": True,
                        }
                    ],
                    "tools": [
                        {
                            "name": "pytest",
                            "label": "Pytest",
                            "renderer_key": "generic",
                            "permission_category": "command",
                        }
                    ],
                    "agentApplication": {
                        "applicationId": "tests.python",
                        "label": "Python Agent",
                        "profileId": "tests.python.profile",
                        "workflowPackageIds": ["workflow-python"],
                        "active": True,
                    },
                    "agentApplications": [
                        {
                            "applicationId": "tests.python",
                            "label": "Python Agent",
                            "profileId": "tests.python.profile",
                            "workflowPackageIds": ["workflow-python"],
                            "active": True,
                        }
                    ],
                    "emptyState": {"scenario_label": "Python workspace"},
                },
            }
        )

        self.assertEqual(
            set(payload),
            {
                "schema_version",
                "event_cursor",
                "thread",
                "snapshot",
                "history",
                "capabilities",
                "plan",
                "permission_context",
            },
        )
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["thread"]["id"], "sess-1")
        self.assertEqual(payload["history"]["activities"][0]["kind"], "user")
        self.assertNotIn("turns", payload["history"])
        self.assertNotIn("timeline", payload)
        self.assertEqual(payload["capabilities"]["modes"][0]["id"], "python")
        self.assertEqual(
            payload["capabilities"]["agent_application"]["id"],
            "tests.python",
        )
        self.assertEqual(
            payload["capabilities"]["agent_applications"][0]["profile_id"],
            "tests.python.profile",
        )
        self.assertEqual(
            payload["snapshot"]["workflow_state"]["package_id"],
            "workflow-python",
        )
        self.assertEqual(payload["event_cursor"], 7)
        wire = json.dumps(payload)
        self.assertNotIn("agentApplication", wire)
        self.assertNotIn("currentMode", wire)

    def test_session_bootstrap_does_not_invent_missing_workflow_state(self):
        payload = serialize_session_bootstrap(
            {
                "snapshot": {
                    "session_id": "sess-generic",
                    "status": "idle",
                    "current_mode": "python-build",
                },
                "history": {"activities": []},
            }
        )

        self.assertEqual(payload["snapshot"]["workflow_state"], {})
        self.assertNotIn("workflow", payload)
        self.assertEqual(payload["event_cursor"], 0)

    def test_session_bootstrap_rejects_negative_event_cursor(self):
        with self.assertRaisesRegex(ValueError, "event_cursor must be non-negative"):
            serialize_session_bootstrap(
                {
                    "event_cursor": -1,
                    "snapshot": {"session_id": "sess-invalid", "status": "idle"},
                    "history": {"activities": []},
                }
            )

    def test_session_bootstrap_rejects_malformed_capability_records(self):
        with self.assertRaisesRegex(
            ValueError,
            "capabilities.modes contains an invalid item",
        ):
            serialize_session_bootstrap(
                {
                    "snapshot": {"session_id": "sess-invalid", "status": "idle"},
                    "history": {"activities": []},
                    "capabilities": {"modes": ["build"]},
                }
            )

    def test_managed_session_defaults_to_empty_workflow_state(self):
        managed = ManagedSession(session_id="sess-managed", current_mode="")

        self.assertEqual(managed.workflow_state, "")

    def test_app_bootstrap_is_app_shell_only(self):
        payload = serialize_app_bootstrap(
            {
                "app": {"product_name": "EmbedAgent"},
                "workspaces": [{"id": "ws-1", "label": "demo"}],
                "active_workspace": {"id": "ws-1", "label": "demo"},
                "has_active_workspace": True,
                "shell": {
                    "schema_version": 2,
                    "commands": [
                        {
                            "id": "app.open",
                            "label": "Open",
                            "group": "app",
                            "dispatch": {"kind": "workspace.open"},
                        }
                    ],
                    "surfaces": [],
                    "keybindings": [],
                    "tool_presentations": [],
                    "timeline_items": [],
                    "interactions": [],
                },
                "settings": {"confirm_workspace_switch": True},
                "diagnostics": {"offline": True},
                "last_failure": None,
                "history": {"activities": []},
            }
        )

        self.assertEqual(
            set(payload),
            {
                "schema_version",
                "app",
                "workspaces",
                "active_workspace",
                "has_active_workspace",
                "shell",
                "settings",
                "diagnostics",
                "last_failure",
            },
        )
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["app"]["product_name"], "EmbedAgent")
        self.assertEqual(payload["active_workspace"]["id"], "ws-1")
        self.assertEqual(
            payload["shell"]["commands"][0]["dispatch"]["kind"],
            "workspace.open",
        )
        self.assertNotIn("history", payload)
        self.assertNotIn("snapshot", payload)


if __name__ == "__main__":
    unittest.main()
