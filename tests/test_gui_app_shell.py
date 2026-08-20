import os
import tempfile
import unittest

from embedagent_protocol import (
    AgentApplicationDescriptor,
    CapabilitySnapshot,
    CommandDescriptor,
    KeybindingDescriptor,
    ShellDescriptor,
    SurfaceDescriptor,
)

from embedagent.frontend.gui.backend.app_host import FrontendPortSet, GUIAppHost
from embedagent.frontend.gui.backend.app_shell import AppShellService
from embedagent.frontend.gui.backend.protocol_payloads import serialize_app_bootstrap
from embedagent.frontend.gui.backend.workspace_registry import WorkspaceRegistry


class _FakeFrontend(object):
    def __init__(self):
        self.messages = []

    def _dispatch_message(self, message):
        self.messages.append(message)
        return True

    def on_session_event(self, envelope):
        del envelope


class _FakePorts(object):
    def __init__(self, workspace):
        self.workspace = workspace
        self.closed = False

    def list_sessions(self, limit=10):
        raise AssertionError("app shell must not read session history")

    def get_session_bootstrap(self, session_id):
        raise AssertionError("app shell must not read session bootstrap")

    def get_session_capabilities(self, session_id=""):
        del session_id
        return _capability_snapshot()

    def get_workspace_snapshot(self):
        return {"path": self.workspace}

    def close(self):
        self.closed = True


def _agent_capabilities():
    return {
        "commands": [
            {
                "name": "review",
                "usage": "/review",
                "summary": "Review changes",
                "source_type": "builtin",
                "source_id": "slash_commands",
                "active": True,
            }
        ],
        "agentApplication": {
            "applicationId": "tests.python",
            "label": "Python Agent",
            "profileId": "tests.python.profile",
            "workflowPackageIds": [],
            "active": True,
        },
        "agentApplications": [
            {
                "applicationId": "tests.python",
                "label": "Python Agent",
                "profileId": "tests.python.profile",
                "workflowPackageIds": [],
                "active": True,
            }
        ],
        "emptyState": {
            "scenario_label": "Python workspace",
            "primary": "Open a Python project",
        },
    }


def _capability_snapshot():
    application = AgentApplicationDescriptor(
        id="tests.python",
        label="Python Agent",
        profile_id="tests.python.profile",
        workflow_package_ids=[],
        active=True,
    )
    return CapabilitySnapshot(
        commands=[
            CommandDescriptor(
                id="review",
                label="/review",
                group="builtin",
                dispatch={},
                summary="Review changes",
                source_type="builtin",
                source_id="slash_commands",
            )
        ],
        agent_application=application,
        agent_applications=[application],
        empty_state={
            "scenario_label": "Python workspace",
            "primary": "Open a Python project",
        },
    )


def _descriptor():
    return ShellDescriptor(
        schema_version=2,
        commands=[
            CommandDescriptor(
                id="session.new",
                label="New Session",
                group="session",
                dispatch={"kind": "session.create"},
            )
        ],
        surfaces=[
            SurfaceDescriptor(
                id="session.commands",
                label="Commands",
                placement="overlay",
                renderer_key="command_palette",
            )
        ],
        keybindings=[KeybindingDescriptor(command_id="session.new", keys="ctrl+n")],
    )


class TestGuiAppShellService(unittest.TestCase):
    def _service(self, registry, created, shell_compiler=None, host_diagnostics=None):
        frontend = _FakeFrontend()

        def factory(path, event_sink):
            port = _FakePorts(path)
            ports = FrontendPortSet(session=port, workspace=port)
            created.append((ports, event_sink))
            return ports

        host = GUIAppHost(
            port_factory=factory,
            event_sink=frontend,
            registry=registry,
            agent_capabilities=_agent_capabilities(),
        )
        calls = []

        def compiler(application_id, capabilities):
            calls.append((application_id, capabilities))
            return _descriptor()

        service = AppShellService(
            host,
            shell_compiler=shell_compiler or compiler,
            host_diagnostics=host_diagnostics
            or {
                "host": {"platform": "win32", "debug": False},
                "runtime": {"runtime_source": "bundle"},
                "renderer": {"renderer": "edgechromium"},
            },
        )
        return service, host, frontend, calls

    def test_bootstrap_compiles_exact_selected_application_shell(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            service, _, _, calls = self._service(registry, [])

            payload = service.bootstrap()

        self.assertEqual(payload["shell"], _descriptor().to_dict())
        self.assertEqual(calls[0][0], "tests.python")
        self.assertEqual(calls[0][1]["commands"][0]["id"], "review")
        self.assertNotIn("capabilities", payload)

    def test_serialized_bootstrap_preserves_compiled_descriptor(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            service, _, _, _ = self._service(registry, [])

            payload = serialize_app_bootstrap(service.bootstrap())

        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["shell"], _descriptor().to_dict())

    def test_compiler_failure_is_not_replaced_with_gui_defaults(self):
        def invalid_compiler(application_id, capabilities):
            raise ValueError("duplicate_shell_command:session.new")

        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            service, _, _, _ = self._service(
                registry,
                [],
                shell_compiler=invalid_compiler,
            )

            with self.assertRaisesRegex(ValueError, "duplicate_shell_command:session.new"):
                service.bootstrap()

    def test_workspace_operations_keep_the_same_compiler_boundary(self):
        with tempfile.TemporaryDirectory() as root:
            workspace = os.path.join(root, "project")
            os.mkdir(workspace)
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            created = []
            service, host, frontend, calls = self._service(registry, created)

            opened = service.open_workspace_path(workspace)
            removed = service.remove_workspace(opened["active_workspace"]["id"])

        self.assertEqual(opened["shell"], _descriptor().to_dict())
        self.assertEqual(removed["shell"], _descriptor().to_dict())
        self.assertGreaterEqual(len(calls), 2)
        self.assertIs(created[0][1], frontend)
        self.assertIsNone(host.current_ports())
        self.assertTrue(created[0][0].session.closed)

    def test_bootstrap_excludes_history_and_secret_diagnostics(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            service, _, _, _ = self._service(
                registry,
                [],
                host_diagnostics={
                    "host": {"platform": "win32", "api_key": "secret"},
                    "runtime": {"authorization": "secret"},
                    "renderer": {"renderer": "edgechromium"},
                    "transcript": "secret",
                },
            )

            payload = service.bootstrap()

        self.assertNotIn("history", payload)
        self.assertNotIn("snapshot", payload)
        self.assertNotIn("secret", str(payload))


if __name__ == "__main__":
    unittest.main()
