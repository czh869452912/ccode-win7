import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.agent_applications import agent_application_capability_payload
from embedagent.frontend.gui.backend.app_host import GUIAppHost
from embedagent.frontend.gui.backend.app_shell import AppShellService
from embedagent.frontend.gui.backend.app_shell_spec import AppShellSpec
from embedagent.frontend.gui.backend.workspace_registry import WorkspaceRegistry


class _FakeFrontend(object):
    def __init__(self):
        self.messages = []

    def _dispatch_message(self, message):
        self.messages.append(message)
        return True


class _FakeCore(object):
    def __init__(self, workspace):
        self.workspace = workspace
        self.frontend = None
        self.shutdown_calls = 0

    def register_frontend(self, frontend):
        self.frontend = frontend

    def shutdown(self):
        self.shutdown_calls += 1

    def list_sessions(self, limit=10):
        raise AssertionError("app shell must not read session history")

    def get_session_bootstrap(self, session_id):
        raise AssertionError("app shell must not read session bootstrap")

    def get_session_capabilities(self, session_id=""):
        return {
            "agentApplication": {
                "applicationId": "tests.python",
                "label": "Python Agent",
                "profileId": "tests.python.profile",
                "workflowPackageIds": ["tests.python.workflow"],
                "active": True,
            },
            "agentApplications": [
                {
                    "applicationId": "tests.python",
                    "label": "Python Agent",
                    "profileId": "tests.python.profile",
                    "workflowPackageIds": ["tests.python.workflow"],
                    "active": True,
                }
            ],
            "emptyState": {
                "scenario_label": "Python workspace",
                "primary": "Open a Python project",
            },
        }

    def get_workspace_snapshot(self):
        return {"path": self.workspace}


class TestGuiAppShellService(unittest.TestCase):
    def _service(
        self,
        registry,
        created,
        host_diagnostics=None,
        shell_spec=None,
        agent_capabilities=None,
    ):
        def factory(path):
            core = _FakeCore(path)
            created.append(core)
            return core

        host = GUIAppHost(
            core_factory=factory,
            registry=registry,
            agent_capabilities=agent_capabilities,
        )
        frontend = _FakeFrontend()
        host.bind_frontend(frontend)
        return (
            AppShellService(
                host,
                host_diagnostics=host_diagnostics
                or {
                    "host": {"platform": "win32", "debug": False},
                    "runtime": {
                        "runtime_source": "bundle",
                        "runtime_path": r"C:\runtime\webview2",
                    },
                    "renderer": {"renderer": "edgechromium"},
                },
                shell_spec=shell_spec,
            ),
            host,
            frontend,
        )

    def test_bootstrap_without_workspace_includes_shell_fields(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            service, host, frontend = self._service(registry, [])

            payload = service.bootstrap()

        self.assertEqual(payload["app"]["shell_version"], 1)
        self.assertEqual(payload["app"]["protocol"], "gui_app_shell_v1")
        self.assertEqual(payload["app"]["product_name"], "EmbedAgent")
        self.assertEqual(payload["has_active_workspace"], False)
        self.assertIsNone(payload["active_workspace"])
        self.assertEqual(payload["workspaces"], [])
        self.assertIn("app.settings", payload["capabilities"]["app_commands"])
        self.assertIn("app.diagnostics", payload["capabilities"]["app_commands"])
        self.assertIn("app.source_control", payload["capabilities"]["app_commands"])
        self.assertIn("app.reload", payload["capabilities"]["app_commands"])
        keybinding_commands = [
            item["command_id"] for item in payload["capabilities"]["keybindings"]
        ]
        self.assertIn("palette.open", keybinding_commands)
        self.assertIn("surface.files", keybinding_commands)
        self.assertIn("app.settings", keybinding_commands)
        right_panel_surfaces = [
            item["id"] for item in payload["capabilities"]["surfaces"]["right_panel"]
        ]
        self.assertIn("settings", right_panel_surfaces)
        self.assertIn("diagnostics", right_panel_surfaces)
        self.assertIn("source_control", right_panel_surfaces)
        self.assertEqual(
            payload["capabilities"]["surfaces"]["right_panel"][0]["launcher_order"],
            10,
        )
        self.assertEqual(
            [item["id"] for item in payload["capabilities"]["thread_lifecycle"]["actions"]],
            ["rename", "fork", "archive"],
        )
        self.assertEqual(
            payload["capabilities"]["source_control"],
            {
                "enabled": True,
                "vcs": ["git"],
                "read_only": True,
                "remote_providers": False,
                "network": False,
                "checkpoints": False,
                "requires_active_workspace": True,
            },
        )
        self.assertEqual(
            payload["capabilities"]["terminal"],
            {
                "enabled": True,
                "pty": False,
                "resize": False,
                "history_persistent": False,
                "max_buffer_bytes": 131072,
            },
        )
        bottom_drawer_surfaces = [
            item["id"] for item in payload["capabilities"]["surfaces"]["bottom_drawer"]
        ]
        self.assertIn("terminal", bottom_drawer_surfaces)
        self.assertTrue(payload["settings"]["confirm_workspace_switch"])
        self.assertIn("host", payload["diagnostics"])
        self.assertIn("runtime", payload["diagnostics"])
        self.assertIn("renderer", payload["diagnostics"])
        self.assertIn("workspace_registry", payload["diagnostics"])
        self.assertIn("active_core", payload["diagnostics"])
        self.assertEqual(payload["diagnostics"]["active_core"]["present"], False)
        self.assertIs(host.current_core(), None)
        self.assertEqual(frontend.messages, [])

    def test_bootstrap_without_workspace_projects_selected_agent_application(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            created = []
            service, host, frontend = self._service(
                registry,
                created,
                agent_capabilities=agent_application_capability_payload("embedagent.python"),
            )

            payload = service.bootstrap()

        self.assertEqual(created, [])
        self.assertIs(host.current_core(), None)
        self.assertEqual(frontend.messages, [])
        self.assertEqual(payload["has_active_workspace"], False)
        self.assertEqual(
            payload["capabilities"]["agentApplication"]["applicationId"],
            "embedagent.python",
        )
        self.assertEqual(
            payload["capabilities"]["agentApplications"][0]["applicationId"],
            "embedagent.default_c_cpp",
        )
        self.assertEqual(
            payload["capabilities"]["emptyState"]["scenario_label"],
            "Python workspace",
        )

    def test_bootstrap_uses_injected_app_shell_spec(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            service, _host, _frontend = self._service(
                registry,
                [],
                shell_spec=AppShellSpec(
                    app_commands=("app.settings",),
                    workspace_commands=("workspace.open",),
                    right_panel_surfaces=(
                        {
                            "id": "settings",
                            "title": "Settings",
                            "launcher_order": 10,
                        },
                    ),
                    bottom_drawer_surfaces=(),
                    keybindings=(
                        {
                            "key": "mod+,",
                            "command_id": "app.settings",
                            "when": "always",
                        },
                    ),
                    source_control={"enabled": False},
                    terminal={"enabled": False},
                    thread_lifecycle_actions=(),
                ),
            )

            payload = service.bootstrap()

        self.assertEqual(payload["capabilities"]["app_commands"], ["app.settings"])
        self.assertEqual(payload["capabilities"]["workspace_commands"], ["workspace.open"])
        self.assertEqual(
            [item["id"] for item in payload["capabilities"]["surfaces"]["right_panel"]],
            ["settings"],
        )
        self.assertEqual(payload["capabilities"]["surfaces"]["bottom_drawer"], [])
        self.assertEqual(
            payload["capabilities"]["keybindings"],
            [{"key": "mod+,", "command_id": "app.settings", "when": "always"}],
        )
        self.assertEqual(payload["capabilities"]["source_control"], {"enabled": False})
        self.assertEqual(payload["capabilities"]["thread_lifecycle"], {"actions": []})

    def test_open_workspace_returns_app_shell_payload_and_binds_core(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            workspace = os.path.join(root, "project-a")
            os.mkdir(workspace)
            created = []
            service, host, frontend = self._service(registry, created)

            payload = service.open_workspace_path(workspace)

        self.assertEqual(payload["active_workspace"]["path"], os.path.realpath(workspace))
        self.assertEqual(payload["has_active_workspace"], True)
        self.assertEqual(
            payload["capabilities"]["agentApplication"]["applicationId"],
            "tests.python",
        )
        self.assertEqual(
            payload["capabilities"]["agentApplications"][0]["profileId"],
            "tests.python.profile",
        )
        self.assertEqual(
            payload["capabilities"]["emptyState"]["scenario_label"],
            "Python workspace",
        )
        self.assertEqual(payload["diagnostics"]["active_core"]["present"], True)
        self.assertEqual(payload["diagnostics"]["workspace_registry"]["count"], 1)
        self.assertEqual(len(created), 1)
        self.assertIs(created[0].frontend, frontend)
        self.assertIs(host.current_core(), created[0])
        self.assertEqual(frontend.messages[-1]["type"], "workspace_changed")

    def test_removed_workspace_payload_keeps_shell_fields(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            workspace = os.path.join(root, "project-a")
            os.mkdir(workspace)
            created = []
            service, host, _frontend = self._service(registry, created)
            opened = service.open_workspace_path(workspace)

            payload = service.remove_workspace(opened["active_workspace"]["id"])

        self.assertEqual(payload["removed"], True)
        self.assertEqual(payload["workspaces"], [])
        self.assertIsNone(payload["active_workspace"])
        self.assertEqual(payload["has_active_workspace"], False)
        self.assertEqual(payload["diagnostics"]["active_core"]["present"], False)
        self.assertIn("app", payload)
        self.assertIn("capabilities", payload)
        self.assertIn("settings", payload)
        self.assertEqual(created[0].shutdown_calls, 1)
        self.assertIs(host.current_core(), None)

    def test_bootstrap_excludes_session_history_and_secret_fields(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            created = []
            service, _host, _frontend = self._service(
                registry,
                created,
                host_diagnostics={
                    "host": {
                        "platform": "win32",
                        "api_key": "sk-secret",
                        "nested": {"token": "secret-token", "safe": "ok"},
                    },
                    "runtime": {"authorization": "Bearer abc", "runtime_source": "bundle"},
                    "renderer": {"prompt": "hidden prompt", "renderer": "edgechromium"},
                    "transcript": {"messages": ["do not serialize"]},
                    "tool_output": "hidden tool output",
                },
            )

            payload = service.bootstrap()
            serialized = json.dumps(payload, sort_keys=True)

        self.assertNotIn("api_key", serialized)
        self.assertNotIn("sk-secret", serialized)
        self.assertNotIn("token", serialized)
        self.assertNotIn("secret-token", serialized)
        self.assertNotIn("authorization", serialized)
        self.assertNotIn("Bearer abc", serialized)
        self.assertNotIn("hidden prompt", serialized)
        self.assertNotIn("transcript", serialized)
        self.assertNotIn("tool_output", serialized)
        self.assertIn('"safe": "ok"', serialized)
        self.assertEqual(created, [])


if __name__ == "__main__":
    unittest.main()
