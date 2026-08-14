"""Integration coverage for GUI interaction responses through focused ports."""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import time
import unittest

import pytest
from embedagent_core.permissions import PermissionPolicy
from embedagent_host.frontend_ports import (
    InProcessFrontendSessionPort,
    InProcessFrontendWorkspacePort,
)
from embedagent_host.inprocess_adapter import InProcessAdapter
from embedagent_host.runtime.session_store import SessionSummaryStore
from embedagent_host.runtime.tools import ToolRuntime
from embedagent_protocol import ShellDescriptor
from test_inprocess_adapter_frontend_api import AskUserClient

from embedagent.frontend.gui.backend.app_host import FrontendPortSet, SingleWorkspaceAppHost
from embedagent.frontend.gui.backend.server import GUIBackend, WebSocketFrontend
from embedagent.product_catalog import product_agent_application_registry


@pytest.mark.gui
class TestGuiSync(unittest.TestCase):
    def test_gui_backend_route_resolves_pending_input_interaction(self):
        workspace = tempfile.mkdtemp(prefix="gui-sync-")
        static_dir = tempfile.mkdtemp(prefix="gui-sync-static-")
        try:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            frontend = WebSocketFrontend()
            adapter = InProcessAdapter(
                client=AskUserClient(),
                tools=ToolRuntime(workspace),
                max_turns=8,
                permission_policy=PermissionPolicy(auto_approve_all=True, workspace=workspace),
                summary_store=SessionSummaryStore(workspace),
                event_sink=frontend,
                agent_application_registry=product_agent_application_registry(),
            )
            session = InProcessFrontendSessionPort(adapter)
            ports = FrontendPortSet(session, InProcessFrontendWorkspacePort(adapter))
            backend = GUIBackend(
                static_dir=static_dir,
                app_host=SingleWorkspaceAppHost(ports),
                frontend=frontend,
                shell_compiler=lambda application_id, capabilities: ShellDescriptor(),
            )
            frontend._dispatch_message = lambda message: True

            created = session.create_session("spec")
            session_id = created.thread.id
            session.submit_user_message(session_id, "请继续", True)

            deadline = time.time() + 3.0
            interaction_id = ""
            while time.time() < deadline:
                snapshot = session.get_session_bootstrap(session_id).snapshot
                pending = snapshot.get("pending_interaction") or {}
                if pending.get("kind") == "user_input":
                    interaction_id = str(pending.get("interaction_id") or "")
                    break
                time.sleep(0.02)

            self.assertTrue(interaction_id)
            route = next(
                item
                for item in backend.app.routes
                if getattr(item, "path", "")
                == "/api/sessions/{session_id}/interactions/{interaction_id}/respond"
            )
            asyncio.run(
                route.endpoint(
                    session_id,
                    interaction_id,
                    {"answers": {"answer": "切到 debug 模式继续排查"}},
                )
            )

            deadline = time.time() + 3.0
            current = None
            while time.time() < deadline:
                current = session.get_session_bootstrap(session_id).snapshot
                if (
                    current.get("pending_interaction") is None
                    and current.get("current_mode") == "debug"
                ):
                    break
                time.sleep(0.02)
            self.assertIsNotNone(current)
            self.assertIsNone(current.get("pending_interaction"))
            self.assertEqual(current.get("current_mode"), "debug")
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
            shutil.rmtree(static_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
