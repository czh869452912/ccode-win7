import asyncio
import json
import os
import sys
import threading
import tempfile
import unittest
from unittest.mock import ANY, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.config import AppConfig
from embedagent.frontend.gui.backend.bridge import BlockingResult, ThreadsafeAsyncDispatcher
from embedagent.frontend.gui.backend.server import GUIBackend, WebSocketFrontend
from embedagent.frontend.gui import launcher as gui_launcher


class TestGuiLauncher(unittest.TestCase):
    def test_create_core_uses_flat_config_and_runtime_policies(self):
        app_config = AppConfig(
            base_url="http://internal/v1",
            api_key="sk-internal",
            model="qwen3.5-coder",
            timeout=45,
            max_turns=11,
        )
        with tempfile.TemporaryDirectory() as workspace:
            real_workspace = os.path.realpath(workspace)
            with patch("embedagent.config.load_config", return_value=app_config), \
                 patch("embedagent.llm.OpenAICompatibleClient") as client_cls, \
                 patch("embedagent.tools.ToolRuntime") as tools_cls, \
                 patch("embedagent.context.make_context_config", return_value="context-config") as make_context_config, \
                 patch("embedagent.context.ContextManager") as context_manager_cls, \
                 patch("embedagent.project_memory.ProjectMemoryStore") as memory_store_cls, \
                 patch("embedagent.permissions.PermissionPolicy") as permission_policy_cls, \
                 patch("embedagent.core.adapter.AgentCoreAdapter") as adapter_cls:
                core = gui_launcher.create_core(
                    workspace,
                    {
                        "approve_commands": True,
                        "permission_rules": ".embedagent/permission-rules.json",
                    },
                )

            self.assertIs(core, adapter_cls.return_value)
            client_cls.assert_called_once_with(
                base_url="http://internal/v1",
                api_key="sk-internal",
                model="qwen3.5-coder",
                timeout=45.0,
            )
            tools_cls.assert_called_once_with(workspace=real_workspace, app_config=app_config)
            make_context_config.assert_called_once_with(app_config)
            memory_store_cls.assert_called_once_with(real_workspace)
            context_manager_cls.assert_called_once_with(
                config="context-config",
                project_memory=memory_store_cls.return_value,
            )
            permission_policy_cls.assert_called_once_with(
                auto_approve_all=False,
                auto_approve_writes=False,
                auto_approve_commands=True,
                workspace=real_workspace,
                rules_path=".embedagent/permission-rules.json",
            )
            adapter_cls.assert_called_once_with(workspace=real_workspace, config=ANY)
            adapter_cls.return_value.initialize.assert_called_once_with(
                client=client_cls.return_value,
                tools=tools_cls.return_value,
                max_turns=11,
                permission_policy=permission_policy_cls.return_value,
                context_manager=context_manager_cls.return_value,
            )

    def test_main_accepts_workspace_option(self):
        with tempfile.TemporaryDirectory() as workspace:
            with patch.object(gui_launcher, "launch_gui") as launch_gui:
                exit_code = gui_launcher.main(["--workspace", workspace, "--model", "qwen3.5-coder"])
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
    def register_frontend(self, frontend):
        self.frontend = frontend

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
                "_timeline_event": {
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

    def test_dispatch_result_reason_is_logged_when_queueing_fails(self):
        frontend = WebSocketFrontend()
        frontend._dispatcher.dispatch = lambda factory: type("Result", (), {"queued": False, "reason": "loop_closed", "__bool__": lambda self: False})()
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
            with self.assertLogs("embedagent.frontend.gui.backend.server", level="ERROR") as captured:
                asyncio.run(route.endpoint(websocket))
            self.assertTrue(websocket.accepted)
            self.assertNotIn(websocket, backend.frontend.connections)
            self.assertTrue(any("Unhandled websocket failure" in entry for entry in captured.output))


class TestAgentCoreAdapterApi(unittest.TestCase):
    def test_build_structured_timeline_delegates_to_inner_adapter(self):
        from embedagent.core.adapter import AgentCoreAdapter

        core = AgentCoreAdapter(workspace="D:\\workspace")
        core._adapter = MagicMock()
        core._adapter.build_structured_timeline.return_value = {
            "session_id": "sess-1",
            "turns": [{"turn_id": "turn-1", "steps": []}],
        }

        payload = core.build_structured_timeline("sess-1", limit=55)

        self.assertEqual(payload["session_id"], "sess-1")
        core._adapter.build_structured_timeline.assert_called_once_with("sess-1", limit=55)

    def test_snapshot_projection_preserves_replay_metadata(self):
        from embedagent.core.adapter import AgentCoreAdapter

        core = AgentCoreAdapter(workspace="D:\\workspace")
        core._adapter = MagicMock()
        core._adapter.get_session_snapshot.return_value = {
            "session_id": "sess-1",
            "status": "idle",
            "current_mode": "code",
            "started_at": "2026-04-04T00:00:00Z",
            "updated_at": "2026-04-04T00:00:01Z",
            "timeline_replay_status": "degraded",
            "timeline_first_seq": 2,
            "timeline_last_seq": 6,
            "timeline_integrity": "degraded",
            "pending_interaction_valid": False,
            "restore_stop_reason": "transcript_missing",
        }

        snapshot = core.get_session_snapshot("sess-1")

        self.assertEqual(snapshot.timeline_replay_status, "degraded")
        self.assertEqual(snapshot.timeline_first_seq, 2)
        self.assertEqual(snapshot.timeline_last_seq, 6)
        self.assertEqual(snapshot.timeline_integrity, "degraded")
        self.assertFalse(snapshot.pending_interaction_valid)
        self.assertEqual(snapshot.restore_stop_reason, "transcript_missing")


if __name__ == "__main__":
    unittest.main()
