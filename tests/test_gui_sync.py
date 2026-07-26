"""Tests for GUI read-model invalidation sync callbacks."""

import os
import shutil
import sys
import tempfile
import time
import unittest

import pytest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_core.permissions import PermissionPolicy
from embedagent_host.runtime.tools import ToolRuntime


@pytest.mark.gui
class TestGuiSync(unittest.TestCase):
    def test_gui_backend_route_resolves_core_pending_input_interaction(self):
        import asyncio

        from test_inprocess_adapter_frontend_api import AskUserClient

        from embedagent.core.adapter import AgentCoreAdapter
        from embedagent.frontend.gui.backend.server import GUIBackend

        workspace = tempfile.mkdtemp(prefix="gui-sync-")
        static_dir = tempfile.mkdtemp(prefix="gui-sync-static-")
        try:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            tools = ToolRuntime(workspace)
            core = AgentCoreAdapter(workspace=workspace)
            core.initialize(
                client=AskUserClient(),
                tools=tools,
                max_turns=8,
                permission_policy=PermissionPolicy(auto_approve_all=True, workspace=workspace),
            )
            backend = GUIBackend(core, static_dir=static_dir)
            backend.frontend._dispatch_message = lambda message: True

            snapshot = core.create_session("spec")
            session_id = snapshot.session_id

            core.submit_message(session_id, "请继续")
            deadline = time.time() + 3.0
            interaction_id = ""
            while time.time() < deadline:
                current_snapshot = core.get_session_snapshot(session_id)
                pending = current_snapshot.pending_interaction or {}
                if pending.get("kind") == "user_input":
                    interaction_id = str(pending.get("interaction_id") or "")
                    break
                time.sleep(0.02)

            self.assertTrue(interaction_id)
            route = None
            for item in backend.app.routes:
                if getattr(
                    item, "path", ""
                ) == "/api/sessions/{session_id}/interactions/{interaction_id}/respond" and "POST" in getattr(
                    item, "methods", set()
                ):
                    route = item
                    break
            self.assertIsNotNone(route)
            asyncio.run(
                route.endpoint(
                    session_id,
                    interaction_id,
                    {"answers": {"answer": "切到 debug 模式继续排查"}},
                )
            )

            deadline = time.time() + 3.0
            current_snapshot = None
            while time.time() < deadline:
                current_snapshot = core.get_session_snapshot(session_id)
                if (
                    current_snapshot.pending_interaction is None
                    and current_snapshot.current_mode == "debug"
                ):
                    break
                time.sleep(0.02)
            self.assertIsNotNone(current_snapshot)
            self.assertIsNone(current_snapshot.pending_interaction)
            self.assertEqual(current_snapshot.current_mode, "debug")
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
            shutil.rmtree(static_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
