import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.core.adapter import _session_snapshot_from_dict
from embedagent.frontend.gui.backend.protocol_payloads import (
    serialize_app_bootstrap,
    serialize_session_bootstrap,
)
from embedagent.session_runtime import ManagedSession
from embedagent_core.session import Session


class GuiProtocolProjectionTests(unittest.TestCase):
    def test_session_bootstrap_uses_protocol_history_activities_only(self):
        payload = serialize_session_bootstrap(
            {
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
                    "modes": [{"id": "python", "label": "Python", "commandId": "mode.python"}],
                    "commands": [{"id": "mode.python", "label": "Python", "group": "mode"}],
                    "tools": [{"name": "pytest", "label": "Pytest"}],
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

        self.assertEqual(payload["thread"]["id"], "sess-1")
        self.assertEqual(payload["history"]["activities"][0]["kind"], "user")
        self.assertNotIn("turns", payload["history"])
        self.assertNotIn("timeline", payload)
        self.assertEqual(payload["capabilities"]["modes"][0]["id"], "python")
        self.assertEqual(
            payload["capabilities"]["agentApplication"]["applicationId"],
            "tests.python",
        )
        self.assertEqual(
            payload["capabilities"]["agentApplications"][0]["profileId"],
            "tests.python.profile",
        )
        self.assertEqual(payload["workflow"]["package_id"], "workflow-python")

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

        self.assertEqual(payload["snapshot"]["workflow_state"], "")
        self.assertEqual(payload["workflow"], {})

    def test_core_adapter_does_not_invent_missing_workflow_state(self):
        snapshot = _session_snapshot_from_dict({})

        self.assertEqual(snapshot.workflow_state, "")

    def test_managed_session_defaults_to_empty_workflow_state(self):
        managed = ManagedSession(session=Session(), current_mode="")

        self.assertEqual(managed.workflow_state, "")

    def test_app_bootstrap_is_app_shell_only(self):
        payload = serialize_app_bootstrap(
            {
                "app": {"name": "EmbedAgent"},
                "workspaces": [{"id": "ws-1", "label": "demo"}],
                "commands": [{"id": "app.open", "label": "Open", "group": "app"}],
                "surfaces": [{"id": "chat", "label": "Chat"}],
                "diagnostics": {"offline": True},
                "history": {"activities": []},
            }
        )

        self.assertEqual(payload["app"]["name"], "EmbedAgent")
        self.assertNotIn("history", payload)
        self.assertNotIn("snapshot", payload)


if __name__ == "__main__":
    unittest.main()
