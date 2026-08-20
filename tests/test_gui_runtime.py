from __future__ import annotations

import asyncio
import json
import os
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

from embedagent_protocol import SessionEventEnvelope, ShellDescriptor

from embedagent.frontend.gui import launcher as gui_launcher
from embedagent.frontend.gui.backend.app_host import FrontendPortSet, SingleWorkspaceAppHost
from embedagent.frontend.gui.backend.bridge import ThreadsafeAsyncDispatcher
from embedagent.frontend.gui.backend.server import GUIBackend, WebSocketFrontend


class EmptySessionPort(object):
    def get_session_bootstrap(self, reference, mode=""):
        del reference, mode
        return None

    def get_session_capabilities(self, session_id=""):
        del session_id
        from embedagent_protocol import CapabilitySnapshot

        return CapabilitySnapshot()

    def close(self):
        return None


class EmptyWorkspacePort(object):
    def __init__(self, path):
        self.path = path

    def get_workspace_snapshot(self):
        return {"path": self.path}


def _backend(static_dir):
    ports = FrontendPortSet(EmptySessionPort(), EmptyWorkspacePort(static_dir))
    return GUIBackend(
        static_dir=static_dir,
        app_host=SingleWorkspaceAppHost(ports),
        shell_compiler=lambda application_id, capabilities: ShellDescriptor(),
    )


class TestGuiLauncher(unittest.TestCase):
    def test_launch_gui_constructs_backend_through_current_frontend_ports(self):
        backend_type = MagicMock(side_effect=RuntimeError("stop after backend construction"))
        with patch.object(gui_launcher, "check_dependencies", return_value=True), patch.object(
            gui_launcher,
            "_configure_webview_runtime",
            return_value={
                "runtime_path": "",
                "runtime_source": "test",
                "bundle_required": False,
            },
        ), patch(
            "embedagent.frontend.gui.backend.server.GUIBackend",
            backend_type,
        ):
            with self.assertRaisesRegex(RuntimeError, "stop after backend construction"):
                gui_launcher.launch_gui(
                    headless=True,
                    agent_application_id="embedagent.generic",
                )

        self.assertNotIn("core", backend_type.call_args.kwargs)
        self.assertIn("app_host", backend_type.call_args.kwargs)
        self.assertIn("frontend", backend_type.call_args.kwargs)

    def test_create_frontend_ports_delegates_to_hosted_runtime_with_event_sink(self):
        with tempfile.TemporaryDirectory() as workspace:
            real_workspace = os.path.realpath(workspace)
            hosted_runtime = MagicMock()
            event_sink = MagicMock()
            with patch(
                "embedagent.frontend.gui.launcher.resolve_launch_config",
                return_value=MagicMock(workspace=real_workspace),
            ) as resolve_config, patch(
                "embedagent.frontend.gui.launcher.create_hosted_runtime",
                return_value=hosted_runtime,
            ) as create_runtime:
                ports = gui_launcher.create_frontend_ports(
                    workspace,
                    event_sink,
                    {
                        "approve_commands": True,
                        "permission_rules": ".embedagent/permission-rules.json",
                    },
                )

        self.assertIs(ports.session, hosted_runtime.session)
        self.assertIs(ports.workspace, hosted_runtime.workspace)
        self.assertEqual(resolve_config.call_args.args[0], real_workspace)
        self.assertTrue(resolve_config.call_args.kwargs["overrides"].approve_commands)
        self.assertEqual(resolve_config.call_args.kwargs["overrides"].max_turns, None)
        self.assertIs(create_runtime.call_args.kwargs["event_sink"], event_sink)

    def test_create_frontend_ports_accepts_explicit_runtime_safety_limit(self):
        with tempfile.TemporaryDirectory() as workspace, patch(
            "embedagent.frontend.gui.launcher.resolve_launch_config",
            return_value=MagicMock(workspace=os.path.realpath(workspace)),
        ) as resolve_config, patch(
            "embedagent.frontend.gui.launcher.create_hosted_runtime",
            return_value=MagicMock(),
        ):
            gui_launcher.create_frontend_ports(workspace, MagicMock(), {"max_turns": 3})

        self.assertEqual(resolve_config.call_args.kwargs["overrides"].max_turns, 3)

    def test_create_frontend_ports_uses_user_config_when_option_omitted(self):
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as config_dir:
            with open(os.path.join(config_dir, "config.json"), "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "base_url": "http://user-config/v1",
                        "api_key": "sk-user-config",
                        "model": "user-config-model",
                        "timeout": 33,
                    },
                    handle,
                )
            launch_configs = []

            def fake_create_runtime(launch_config, event_sink=None):
                del event_sink
                launch_configs.append(launch_config)
                return MagicMock()

            with patch("embedagent.config._USER_CONFIG_DIR", config_dir), patch(
                "embedagent.frontend.gui.launcher.create_hosted_runtime",
                side_effect=fake_create_runtime,
            ):
                gui_launcher.create_frontend_ports(workspace, MagicMock(), {})

        self.assertEqual(launch_configs[0].model, "user-config-model")
        self.assertEqual(launch_configs[0].base_url, "http://user-config/v1")
        self.assertEqual(launch_configs[0].timeout, 33)

    def test_main_accepts_workspace_option(self):
        with tempfile.TemporaryDirectory() as workspace, patch.object(
            gui_launcher, "launch_gui"
        ) as launch_gui:
            exit_code = gui_launcher.main(
                [
                    "--workspace",
                    workspace,
                    "--model",
                    "qwen3.5-coder",
                    "--agent-application",
                    "tests.python",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(launch_gui.call_args.kwargs["workspace"], os.path.abspath(workspace))
        self.assertEqual(launch_gui.call_args.kwargs["model"], "qwen3.5-coder")


class TestThreadsafeAsyncDispatcher(unittest.TestCase):
    async def _noop(self):
        return None

    def test_dispatch_requires_bound_loop(self):
        dispatcher = ThreadsafeAsyncDispatcher()
        result = dispatcher.dispatch(lambda: self._noop())
        self.assertFalse(result)
        self.assertEqual(result.reason, "loop_missing")

    def test_dispatch_runs_coroutine_on_bound_loop(self):
        dispatcher = ThreadsafeAsyncDispatcher()
        loop = asyncio.new_event_loop()
        ready = threading.Event()
        done = threading.Event()
        results = []

        def run_loop():
            asyncio.set_event_loop(loop)
            dispatcher.set_loop(loop)
            ready.set()
            loop.run_forever()

        thread = threading.Thread(target=run_loop)
        thread.start()
        try:
            self.assertTrue(ready.wait(1.0))

            async def work():
                results.append("ok")
                done.set()

            result = dispatcher.dispatch(lambda: work())
            self.assertTrue(result)
            self.assertTrue(done.wait(1.0))
            self.assertEqual(results, ["ok"])
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(1.0)
            loop.close()


class FakeWebSocket(object):
    def __init__(self, on_send=None, receive_error=None):
        self.on_send = on_send
        self.receive_error = receive_error
        self.messages = []
        self.accepted = False

    async def accept(self):
        self.accepted = True

    async def send_json(self, message):
        self.messages.append(message)
        if self.on_send is not None:
            self.on_send()

    async def receive_json(self):
        raise self.receive_error or RuntimeError("closed")


class TestWebSocketFrontend(unittest.TestCase):
    def test_broadcast_tolerates_connection_set_mutation(self):
        frontend = WebSocketFrontend()
        late = FakeWebSocket()
        first = FakeWebSocket(on_send=lambda: frontend.disconnect(late))
        frontend.connections = set([first, late])

        asyncio.run(frontend.broadcast({"type": "ping"}))

        self.assertEqual(first.messages, [{"type": "ping"}])
        self.assertEqual(late.messages, [{"type": "ping"}])
        self.assertNotIn(late, frontend.connections)

    def test_session_event_is_forwarded_without_metadata_changes(self):
        frontend = WebSocketFrontend()
        dispatched = []
        frontend._dispatch_message = lambda message: dispatched.append(message) or True
        envelope = SessionEventEnvelope(
            schema_version=2,
            event_id="event-1",
            session_id="session-1",
            sequence=4,
            event_kind="approval.requested",
            timestamp="2026-08-13T00:00:00Z",
            payload={"interaction_id": "approval-1"},
        )

        frontend.on_session_event(envelope)

        self.assertEqual(
            dispatched,
            [{"type": "session_event", "data": envelope.to_dict()}],
        )

    def test_websocket_endpoint_cleans_up_after_receive_failure(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            backend = _backend(static_dir)
            route = next(item for item in backend.app.routes if getattr(item, "path", "") == "/ws")
            websocket = FakeWebSocket(receive_error=RuntimeError("boom"))

            with self.assertLogs(
                "embedagent.frontend.gui.backend.server", level="ERROR"
            ) as captured:
                asyncio.run(route.endpoint(websocket))

        self.assertTrue(websocket.accepted)
        self.assertNotIn(websocket, backend.frontend.connections)
        self.assertTrue(any("Unhandled websocket failure" in item for item in captured.output))


if __name__ == "__main__":
    unittest.main()
