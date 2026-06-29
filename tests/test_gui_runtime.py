import asyncio
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest.mock import ANY, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.core.adapter import CallbackBridge
from embedagent.frontend.gui import launcher as gui_launcher
from embedagent.frontend.gui.backend.bridge import BlockingResult, ThreadsafeAsyncDispatcher
from embedagent.frontend.gui.backend.server import GUIBackend, WebSocketFrontend
from embedagent.protocol import PermissionRequest


class TestGuiLauncher(unittest.TestCase):
    def test_create_core_delegates_runtime_construction_to_hosted_runtime(self):
        with tempfile.TemporaryDirectory() as workspace:
            real_workspace = os.path.realpath(workspace)
            hosted_runtime = MagicMock()
            hosted_runtime.session_host.adapter = MagicMock(name="inner_adapter")
            with patch(
                "embedagent.frontend.gui.launcher.resolve_launch_config",
                return_value=MagicMock(workspace=real_workspace),
            ) as resolve_config, patch(
                "embedagent.frontend.gui.launcher.create_hosted_runtime",
                return_value=hosted_runtime,
            ) as create_hosted_runtime, patch(
                "embedagent.core.adapter.AgentCoreAdapter"
            ) as adapter_cls:
                core = gui_launcher.create_core(
                    workspace,
                    {
                        "approve_commands": True,
                        "permission_rules": ".embedagent/permission-rules.json",
                    },
                )

            self.assertIs(core, adapter_cls.return_value)
            self.assertEqual(resolve_config.call_args.args[0], real_workspace)
            self.assertTrue(resolve_config.call_args.kwargs["overrides"].approve_commands)
            self.assertEqual(
                resolve_config.call_args.kwargs["overrides"].permission_rules,
                ".embedagent/permission-rules.json",
            )
            create_hosted_runtime.assert_called_once()
            adapter_cls.assert_called_once_with(workspace=real_workspace, config=ANY)
            adapter_cls.return_value.attach_adapter.assert_called_once_with(
                hosted_runtime.session_host.adapter
            )

    def test_create_core_accepts_explicit_runtime_safety_limit(self):
        with tempfile.TemporaryDirectory() as workspace:
            hosted_runtime = MagicMock()
            hosted_runtime.session_host.adapter = MagicMock(name="inner_adapter")
            with patch(
                "embedagent.frontend.gui.launcher.resolve_launch_config",
                return_value=MagicMock(workspace=os.path.realpath(workspace)),
            ) as resolve_config, patch(
                "embedagent.frontend.gui.launcher.create_hosted_runtime",
                return_value=hosted_runtime,
            ), patch(
                "embedagent.core.adapter.AgentCoreAdapter"
            ):
                gui_launcher.create_core(workspace, {"max_turns": 3})

            self.assertEqual(resolve_config.call_args.kwargs["overrides"].max_turns, 3)

    def test_main_accepts_workspace_option(self):
        with tempfile.TemporaryDirectory() as workspace:
            with patch.object(gui_launcher, "launch_gui") as launch_gui:
                exit_code = gui_launcher.main(
                    ["--workspace", workspace, "--model", "qwen3.5-coder"]
                )
        self.assertEqual(exit_code, 0)
        launch_gui.assert_called_once()
        self.assertEqual(launch_gui.call_args.kwargs["workspace"], os.path.abspath(workspace))
        self.assertEqual(launch_gui.call_args.kwargs["model"], "qwen3.5-coder")

    def test_config_template_uses_flat_runtime_schema(self):
        template_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "config",
            "config.json.template",
        )
        with open(template_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertIn("base_url", payload)
        self.assertIn("model", payload)
        self.assertNotIn("llm", payload)
        self.assertNotIn("context", payload)


class TestBlockingResult(unittest.TestCase):
    def test_wait_returns_resolved_value(self):
        waiter = BlockingResult(False)

        def resolve_later():
            waiter.resolve(True)

        thread = threading.Thread(target=resolve_later)
        thread.start()
        try:
            self.assertTrue(waiter.wait(1.0))
        finally:
            thread.join(1.0)

    def test_wait_times_out_to_default(self):
        waiter = BlockingResult("fallback")
        self.assertEqual(waiter.wait(0.01), "fallback")


class TestThreadsafeAsyncDispatcher(unittest.TestCase):
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
            self.assertEqual(result.reason, "")
            self.assertTrue(done.wait(1.0))
            self.assertEqual(results, ["ok"])
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(1.0)
            loop.close()

    def test_dispatch_reports_closed_loop_reason(self):
        dispatcher = ThreadsafeAsyncDispatcher()
        loop = asyncio.new_event_loop()
        loop.close()
        dispatcher.set_loop(loop)
        result = dispatcher.dispatch(lambda: self._noop())
        self.assertFalse(result)
        self.assertEqual(result.reason, "loop_closed")

    async def _noop(self):
        return None


class _FakeWebSocket(object):
    def __init__(self, on_send=None):
        self.on_send = on_send
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)
        if self.on_send is not None:
            self.on_send()


class _ReceiveErrorWebSocket(object):
    def __init__(self, exc):
        self._exc = exc
        self.accepted = False

    async def accept(self):
        self.accepted = True

    async def receive_json(self):
        raise self._exc


class _BackendCore(object):
    def __init__(self):
        self.remember_calls = []

    def register_frontend(self, frontend):
        self.frontend = frontend

    def remember_permission_category(self, session_id, category):
        self.remember_calls.append((session_id, category))
        return {
            "session_id": session_id,
            "status": "idle",
            "current_mode": "build",
            "remembered": category,
        }

    def shutdown(self):
        return None


class TestWebSocketFrontend(unittest.TestCase):
    def test_broadcast_tolerates_connection_set_mutation(self):
        frontend = WebSocketFrontend()
        late = _FakeWebSocket()
        first = _FakeWebSocket(on_send=lambda: frontend.disconnect(late))
        frontend.connections = set([first, late])

        asyncio.run(frontend.broadcast({"type": "ping"}))

        self.assertEqual(first.messages, [{"type": "ping"}])
        self.assertEqual(late.messages, [{"type": "ping"}])
        self.assertNotIn(late, frontend.connections)

    def test_on_turn_event_wraps_payload_as_session_event(self):
        frontend = WebSocketFrontend()
        dispatched = []
        frontend._dispatch_message = lambda message: dispatched.append(message) or True

        frontend.on_turn_event(
            "tool_started",
            {
                "session_id": "sess-1",
                "_session_event": {
                    "event_id": "evt-1",
                    "seq": 3,
                    "created_at": "2026-04-04T00:00:00Z",
                    "event": "tool_started",
                },
                "tool_name": "read_file",
                "arguments": {"path": "README.md"},
            },
        )

        self.assertEqual(dispatched[0]["type"], "session_event")
        self.assertEqual(dispatched[0]["data"]["session_id"], "sess-1")
        self.assertEqual(dispatched[0]["data"]["event_kind"], "tool.started")
        self.assertEqual(dispatched[0]["data"]["seq"], 3)

    def test_on_turn_event_generates_metadata_when_core_payload_has_none(self):
        frontend = WebSocketFrontend()
        dispatched = []
        frontend._dispatch_message = lambda message: dispatched.append(message) or True

        frontend.on_turn_event(
            "permission_required",
            {
                "session_id": "sess-1",
                "permission": {
                    "permission_id": "perm-1",
                    "tool_name": "write_file",
                    "category": "workspace_write",
                    "reason": "Allow write",
                },
                "turn_id": "turn-1",
                "step_id": "step-1",
                "step_index": 1,
            },
        )

        event = dispatched[0]["data"]
        self.assertEqual(event["session_id"], "sess-1")
        self.assertEqual(event["event_kind"], "interaction.created")
        self.assertTrue(event["event_id"].startswith("evt-"))
        self.assertEqual(event["seq"], 1)
        self.assertTrue(event["created_at"].endswith("Z"))
        self.assertEqual(event["payload"]["permission"]["permission_id"], "perm-1")

    def test_permission_request_does_not_create_activity_event(self):
        frontend = WebSocketFrontend()
        dispatched = []
        frontend._dispatch_message = lambda message: dispatched.append(message) or False

        result = frontend.on_permission_request(
            PermissionRequest(
                permission_id="perm-1",
                session_id="sess-1",
                tool_name="write_file",
                category="workspace_write",
                reason="Allow write",
            )
        )

        self.assertFalse(result)
        self.assertEqual(dispatched[0]["type"], "permission_request")
        self.assertNotIn("session_event", dispatched[0]["data"])


class TestCallbackBridge(unittest.TestCase):
    def test_interaction_required_events_are_forwarded_to_session_event_stream(self):
        frontend = MagicMock()
        bridge = CallbackBridge(frontend)

        bridge.emit(
            "permission_required",
            "sess-1",
            {
                "permission": {"permission_id": "perm-1", "tool_name": "write_file"},
                "turn_id": "turn-1",
                "step_id": "step-1",
                "step_index": 1,
            },
        )

        frontend.on_turn_event.assert_called_once()
        event_name, payload = frontend.on_turn_event.call_args[0]
        self.assertEqual(event_name, "permission_required")
        self.assertEqual(payload["session_id"], "sess-1")
        self.assertEqual(payload["permission"]["permission_id"], "perm-1")

    def test_command_result_preserves_read_model_invalidations(self):
        frontend = MagicMock()
        bridge = CallbackBridge(frontend)

        bridge.emit(
            "command_result",
            "sess-1",
            {
                "command_name": "resources",
                "success": True,
                "message": "reloaded",
                "data": {"read_model_invalidations": ["capabilities"]},
            },
        )

        result = frontend.on_command_result.call_args[0][0]
        self.assertEqual(result.command_name, "resources")
        self.assertEqual(result.data["read_model_invalidations"], ["capabilities"])


class TestWebSocketFrontendDispatch(unittest.TestCase):
    def test_dispatch_result_reason_is_logged_when_queueing_fails(self):
        frontend = WebSocketFrontend()
        frontend._dispatcher.dispatch = lambda factory: type(
            "Result", (), {"queued": False, "reason": "loop_closed", "__bool__": lambda self: False}
        )()
        with self.assertLogs("embedagent.frontend.gui.backend.server", level="ERROR") as captured:
            queued = frontend._dispatch_message({"type": "session_event", "data": {}})
        self.assertFalse(queued)
        self.assertTrue(any("loop_closed" in entry for entry in captured.output))

    def test_websocket_endpoint_cleans_up_after_receive_failure(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            backend = GUIBackend(_BackendCore(), static_dir=static_dir)
            route = None
            for item in backend.app.routes:
                if getattr(item, "path", "") == "/ws":
                    route = item
                    break
            self.assertIsNotNone(route)
            websocket = _ReceiveErrorWebSocket(RuntimeError("boom"))
            with self.assertLogs(
                "embedagent.frontend.gui.backend.server", level="ERROR"
            ) as captured:
                asyncio.run(route.endpoint(websocket))
            self.assertTrue(websocket.accepted)
            self.assertNotIn(websocket, backend.frontend.connections)
            self.assertTrue(
                any("Unhandled websocket failure" in entry for entry in captured.output)
            )


class TestAgentCoreAdapterApi(unittest.TestCase):
    def test_get_session_bootstrap_delegates_to_inner_adapter(self):
        from embedagent.core.adapter import AgentCoreAdapter

        core = AgentCoreAdapter(workspace="D:\\workspace")
        core._adapter = MagicMock()
        core._adapter.get_session_bootstrap.return_value = {
            "snapshot": {"session_id": "sess-1", "status": "idle", "current_mode": "build"},
            "history": {"session_id": "sess-1", "turns": [], "integrity": {"status": "healthy"}},
            "plan": None,
            "permission_context": {"session_id": "sess-1", "rules": []},
        }

        payload = core.get_session_bootstrap("sess-1")

        self.assertEqual(payload["snapshot"].session_id, "sess-1")
        self.assertEqual(payload["history"]["session_id"], "sess-1")
        core._adapter.get_session_bootstrap.assert_called_once_with("sess-1")

    def test_get_session_capabilities_delegates_to_inner_adapter(self):
        from embedagent.core.adapter import AgentCoreAdapter

        core = AgentCoreAdapter(workspace="D:\\workspace")
        core._adapter = MagicMock()
        core._adapter.get_session_capabilities.return_value = {
            "commands": [{"name": "help", "usage": "/help", "active": True}]
        }

        payload = core.get_session_capabilities()

        self.assertEqual(payload["commands"][0]["usage"], "/help")
        core._adapter.get_session_capabilities.assert_called_once_with(session_id="")

    def test_reload_resources_delegates_to_inner_adapter(self):
        from embedagent.core.adapter import AgentCoreAdapter

        core = AgentCoreAdapter(workspace="D:\\workspace")
        core._adapter = MagicMock()
        core._adapter.reload_resources.return_value = {
            "reason": "api",
            "counts": {"skills": 0, "prompts": 1, "recipes": 0},
        }

        payload = core.reload_resources("sess-1", reason="api")

        self.assertEqual(payload["counts"]["prompts"], 1)
        core._adapter.reload_resources.assert_called_once_with(
            session_id="sess-1",
            reason="api",
        )

    def test_submit_message_uses_core_owned_interaction_lifecycle(self):
        from embedagent.core.adapter import AgentCoreAdapter

        core = AgentCoreAdapter(workspace="D:\\workspace")
        core._adapter = MagicMock()

        core.submit_message("sess-1", "hello")

        core._adapter.submit_user_message.assert_called_once()
        kwargs = core._adapter.submit_user_message.call_args.kwargs
        self.assertIsNone(kwargs["permission_resolver"])
        self.assertIsNone(kwargs["user_input_resolver"])
        self.assertEqual(kwargs["event_handler"], core._on_adapter_event)

    def test_snapshot_projection_drops_timeline_metadata_and_preserves_restore_diagnostics(self):
        from embedagent.core.adapter import AgentCoreAdapter

        core = AgentCoreAdapter(workspace="D:\\workspace")
        core._adapter = MagicMock()
        core._adapter.get_session_snapshot.return_value = {
            "session_id": "sess-1",
            "status": "idle",
            "current_mode": "build",
            "started_at": "2026-04-04T00:00:00Z",
            "updated_at": "2026-04-04T00:00:01Z",
            "pending_interaction_valid": False,
            "restore_stop_reason": "transcript_missing",
            "turn_experience": {
                "status": "blocked",
                "completed": [{"kind": "file_created", "path": "README.md"}],
                "next_steps": ["Run validation for the changed files."],
            },
        }

        snapshot = core.get_session_snapshot("sess-1")

        self.assertFalse(hasattr(snapshot, "timeline" + "_replay_status"))
        self.assertFalse(hasattr(snapshot, "timeline" + "_first_seq"))
        self.assertFalse(hasattr(snapshot, "timeline" + "_last_seq"))
        self.assertFalse(hasattr(snapshot, "timeline" + "_integrity"))
        self.assertFalse(snapshot.pending_interaction_valid)
        self.assertEqual(snapshot.restore_stop_reason, "transcript_missing")
        self.assertEqual(snapshot.turn_experience["status"], "blocked")
        self.assertEqual(snapshot.turn_experience["completed"][0]["path"], "README.md")


if __name__ == "__main__":
    unittest.main()
