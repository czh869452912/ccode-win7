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
from embedagent.frontend.gui.backend.server import WebSocketFrontend
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
        self.assertFalse(dispatcher.dispatch(lambda: self._noop()))

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

            self.assertTrue(dispatcher.dispatch(lambda: work()))
            self.assertTrue(done.wait(1.0))
            self.assertEqual(results, ["ok"])
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(1.0)
            loop.close()

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


if __name__ == "__main__":
    unittest.main()
