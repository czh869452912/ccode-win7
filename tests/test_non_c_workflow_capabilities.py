import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fixtures", "workflow_packages"))

from python_demo import PythonDemoWorkflowPackage

from embedagent.frontend.gui.backend.protocol_payloads import serialize_session_bootstrap


class NonCWorkflowCapabilityTests(unittest.TestCase):
    def test_python_workflow_package_projects_without_gui_code_changes(self):
        package = PythonDemoWorkflowPackage()
        payload = serialize_session_bootstrap(
            {
                "snapshot": {
                    "session_id": "sess-python",
                    "status": "idle",
                    "current_mode": "python-build",
                    "workflow_state": {"package_id": package.package_id},
                },
                "history": {"activities": []},
                "capabilities": package.capability_metadata(),
            }
        )

        self.assertEqual(payload["thread"]["current_mode"], "python-build")
        self.assertEqual(payload["capabilities"]["modes"][0]["id"], "python-explore")
        self.assertEqual(payload["capabilities"]["tools"][0]["label"], "Pytest")
        self.assertEqual(
            payload["capabilities"]["empty_state"]["scenario_label"],
            "Python workspace",
        )
        self.assertNotIn("C/C++", str(payload))
        self.assertNotIn("run_recipe", str(payload))


if __name__ == "__main__":
    unittest.main()
