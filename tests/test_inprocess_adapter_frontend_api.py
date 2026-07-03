import json
import os
import shutil
import sys
import threading
import time
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.tools import ToolDefinition, ToolRuntime
from embedagent_core.model import ModelClientError
from embedagent_core.permissions import PermissionPolicy, PermissionRequest
from embedagent_core.session import Action, AssistantReply, Observation
from embedagent_host.hosted_command_service import HostedCommandService
from embedagent_host.hosted_interaction_service import HostedInteractionService
from embedagent_host.inprocess_adapter import InProcessAdapter, _should_emit_context_compacted

_COUNTER = count(1)


def _make_workspace():
    root = os.path.join(
        os.path.dirname(__file__),
        "..",
        "build",
        "test-sandboxes",
        "adapter-%s-%s" % (os.getpid(), next(_COUNTER)),
    )
    root = os.path.realpath(root)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    return root


class FakeClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        return AssistantReply(content="ok", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None:
            on_text_delta(reply.content)
        return reply


class AskUserClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="ask_user",
                        arguments={
                            "question": "下一步怎么做？",
                            "option_1": "切到 debug 模式继续排查",
                            "option_1_mode": "debug",
                            "option_2": "保持当前模式继续说明",
                        },
                        call_id="call-ask",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="done", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class SwitchModeClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="switch_mode",
                        arguments={"target": "build", "reason": "规格已明确，开始实现。"},
                        call_id="call-switch",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="implemented", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class ToolClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="read_file",
                        arguments={"path": "src/pkg/demo.c"},
                        call_id="call-read-demo",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="done", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class FrontendCatalogDynamicToolExtension(object):
    extension_id = "frontend_catalog_dynamic"
    builtin_extension = False

    def __init__(self):
        self.active = False

    def extension_capabilities(self):
        from embedagent_core.extensions import ExtensionCapability

        return [
            ExtensionCapability("register_tools", self.register_tools),
            ExtensionCapability("allowed_tool_names", self.allowed_tool_names),
        ]

    def register_tools(self, event, context):
        from embedagent_core.extensions import ToolRegistrationResult

        del event

        def handler(arguments):
            return Observation(
                "frontend_intranet_fetch",
                True,
                None,
                {"url": str(arguments.get("url") or "")},
            )

        tool = ToolDefinition(
            name="frontend_intranet_fetch",
            description="Fetch a trusted intranet URL for frontend catalog tests.",
            parameters={
                "type": "object",
                "properties": {"url": {"type": "string"}},
            },
            handler=handler,
            metadata={
                "permission_category": "network",
                "mode_visibility": ["build"],
                "workflow_visibility": ["chat"],
                "read_only": False,
            },
            read_only=False,
        )
        assert context.tool_registry is not None
        return ToolRegistrationResult(tools=[tool], source_id=self.extension_id)

    def allowed_tool_names(self, mode_name, workflow_state="chat"):
        if self.active and mode_name == "build" and workflow_state == "chat":
            return {"frontend_intranet_fetch"}
        return set()


class MultiStepClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                reasoning_content="先读取文件内容。",
                actions=[
                    Action(
                        name="read_file",
                        arguments={"path": "src/pkg/demo.c"},
                        call_id="call-step-1",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(
            content="分析完成，文件结构正常。",
            reasoning_content="读取完成，总结结果。",
            actions=[],
            finish_reason="stop",
        )

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_reasoning_delta is not None and reply.reasoning_content:
            on_reasoning_delta(reply.reasoning_content)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class CompactRetryClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            raise ModelClientError("prompt is too long: context length exceeded")
        return AssistantReply(content="after compact", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class GuardStopClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        return AssistantReply(
            content="",
            actions=[
                Action(
                    name="edit_file",
                    arguments={"path": "src/pkg/missing.c", "old_text": "0", "new_text": "1"},
                    call_id="call-guard-%s" % self.calls,
                )
            ],
            finish_reason="tool_calls",
        )

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        return self.generate(messages, tools=tools)


class WriteThenDoneClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="write_file",
                        arguments={
                            "path": "src/generated_write.c",
                            "content": "int generated_write(void) {\n    return 0;\n}\n",
                            "overwrite": True,
                        },
                        call_id="write-frontend-1",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="written", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class TwoWriteThenDoneClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="write_file",
                        arguments={
                            "path": "src/first_write.c",
                            "content": "int first_write(void) { return 1; }\n",
                            "overwrite": True,
                        },
                        call_id="write-remember-1",
                    )
                ],
                finish_reason="tool_calls",
            )
        if self.calls == 2:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="write_file",
                        arguments={
                            "path": "src/second_write.c",
                            "content": "int second_write(void) { return 2; }\n",
                            "overwrite": True,
                        },
                        call_id="write-remember-2",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="written", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class ThreeFileWriteThenDoneClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls <= 3:
            files = [
                ("README.md", "# Demo\n"),
                ("src/main.c", "int main(void) { return 0; }\n"),
                ("tests/test_demo.py", "def test_demo():\n    assert True\n"),
            ]
            path, content = files[self.calls - 1]
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="write_file",
                        arguments={"path": path, "content": content, "overwrite": False},
                        call_id="write-experience-%s" % self.calls,
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="files created", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class CancellableToolClient(object):
    def __init__(self):
        self.calls = 0
        self.release = threading.Event()

    def generate(self, messages, tools=None):
        self.calls += 1
        self.release.wait(2.0)
        return AssistantReply(
            content="",
            actions=[
                Action(
                    name="read_file",
                    arguments={"path": "src/pkg/demo.c"},
                    call_id="call-cancel-%s" % self.calls,
                )
            ],
            finish_reason="tool_calls",
        )

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        return self.generate(messages, tools=tools)


class TestInProcessAdapterFrontendApis(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace()
        self.tools = ToolRuntime(self.workspace)
        self.adapter = InProcessAdapter(
            client=FakeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        os.makedirs(os.path.join(self.workspace, "src", "pkg"))
        with open(
            os.path.join(self.workspace, "src", "pkg", "demo.c"), "w", encoding="utf-8"
        ) as handle:
            handle.write("int main(void) {\n    return 0;\n}\n")
        os.makedirs(os.path.join(self.workspace, ".embedagent"))
        stored = self.tools.tool_result_store.write_text(
            session_id="session-artifacts",
            tool_call_id="call-artifact-1",
            field_name="stdout",
            text="hello artifact",
        )
        self.tools.projection_db.upsert_tool_result_projection(
            session_id="session-artifacts",
            tool_call_id="call-artifact-1",
            message_id="m-artifact-1",
            tool_name="bash",
            field_name="stdout",
            stored_path=stored.relative_path,
            preview_text=stored.preview_text,
            byte_count=stored.byte_count,
            line_count=stored.line_count,
            content_kind=stored.content_kind,
            created_at="2026-04-05T00:00:00Z",
        )
        self.snapshot = self.adapter.create_session("build")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_workspace_snapshot_and_tree(self):
        payload = self.adapter.get_workspace_snapshot()
        self.assertEqual(payload["workspace"], os.path.realpath(self.workspace))
        tree = self.adapter.list_workspace_tree(path="src", max_depth=2, limit=20)
        paths = [item["path"] for item in tree["items"]]
        self.assertIn("src/pkg", paths)
        self.assertIn("src/pkg/demo.c", paths)
        children = self.adapter.list_workspace_children(path="src", limit=20)
        pkg = [item for item in children["items"] if item["path"] == "src/pkg"][0]
        self.assertTrue(pkg["has_children"])

    def test_workspace_snapshot_does_not_execute_runtime_tools(self):
        original_execute = self.tools.execute
        calls = []

        def forbidden_execute(name, arguments):
            calls.append((name, dict(arguments)))
            raise AssertionError("workspace snapshot must not execute tools")

        self.tools.execute = forbidden_execute
        try:
            payload = self.adapter.get_workspace_snapshot()
        finally:
            self.tools.execute = original_execute

        self.assertEqual(calls, [])
        self.assertEqual(payload["git"]["available"], False)
        self.assertEqual(payload["git"]["branch"], "")

    def test_natural_language_mode_switch_updates_session_without_provider_call(self):
        client = FakeClient()
        adapter = InProcessAdapter(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("explore")

        adapter.submit_user_message(
            session_id=snapshot["session_id"],
            text="切换到build模式",
            stream=False,
            wait=True,
        )
        updated = adapter.get_session_snapshot(snapshot["session_id"])

        self.assertEqual(updated["current_mode"], "build")
        self.assertEqual(client.calls, 0)
        self.assertEqual(updated["last_transition_reason"], "mode_changed")

    def test_read_and_write_workspace_file(self):
        loaded = self.adapter.read_workspace_file("src/pkg/demo.c")
        self.assertIn("return 0;", loaded["content"])
        result = self.adapter.write_workspace_file(
            "src/pkg/demo.c", "int main(void) {\n    return 1;\n}\n"
        )
        self.assertIn("diff_preview", result)
        reloaded = self.adapter.read_workspace_file("src/pkg/demo.c")
        self.assertIn("return 1;", reloaded["content"])

    def test_artifact_and_task_apis(self):
        artifacts = self.adapter.list_artifacts(limit=10)
        self.assertGreaterEqual(len(artifacts), 1)
        payload = self.adapter.read_artifact(artifacts[0]["path"])
        self.assertEqual(payload["kind"], "text")
        tasks = self.adapter.list_tasks(session_id=str(self.snapshot.get("session_id") or ""))
        # No harness state pre-generated on session creation
        self.assertEqual(tasks["count"], 0)

    def test_session_snapshot_exposes_task_items(self):
        self.assertIn("task_items", self.snapshot)
        # No harness state pre-generated on session creation
        self.assertEqual(len(self.snapshot.get("task_items") or []), 0)

    def test_session_snapshot_projects_task_fields_from_workflow_state(self):
        session_id = str(self.snapshot.get("session_id") or "")
        # First submit explicit work to generate task graph
        self.adapter.submit_user_message(
            session_id=session_id,
            text="build the project",
            stream=False,
            wait=True,
        )

        state = self.adapter._sessions[session_id]
        workflow = state.session.workflow_state.get("workflow") or {}
        metadata = workflow.get("metadata") or {}
        self.assertTrue(workflow)
        expected_phase = metadata.get("current_phase")
        expected_discipline = metadata.get("discipline_profile")

        # Now set stale values on state (not on workflow_state)
        stale_phase = "stale:phase"
        stale_discipline = "stale:discipline"
        stale_activity = "stale activity"
        stale_summary = "stale summary"
        state.current_phase = stale_phase
        state.discipline_profile = stale_discipline
        state.current_activity = stale_activity
        state.task_summary = stale_summary
        state.task_items = []

        projected = self.adapter.get_session_snapshot(session_id)

        # Snapshot should project from workflow_state, not from stale state values
        self.assertEqual(projected.get("current_phase"), expected_phase)
        self.assertEqual(projected.get("discipline_profile"), expected_discipline)
        # task_summary should contain the track phases, not the stale summary
        self.assertNotEqual(str(projected.get("task_summary") or ""), stale_summary)
        self.assertGreaterEqual(len(projected.get("task_items") or []), 1)

    def test_session_snapshot_uses_synced_workflow_without_describing_harness(self):
        session_id = str(self.snapshot.get("session_id") or "")
        self.adapter.submit_user_message(
            session_id=session_id,
            text="build the project",
            stream=False,
            wait=True,
        )

        state = self.adapter._sessions[session_id]
        workflow = state.session.workflow_state.get("workflow") or {}
        metadata = workflow.get("metadata") or {}
        expected_phase = metadata.get("current_phase")

        self.assertEqual(metadata.get("current_phase"), expected_phase)

        def fail_describe_mode(*args, **kwargs):
            raise AssertionError("get_session_snapshot should use workflow_state projection")

        self.adapter.harness_workflow.harness_runner.describe_mode = fail_describe_mode

        projected = self.adapter.get_session_snapshot(session_id)

        self.assertEqual(projected.get("current_phase"), expected_phase)
        self.assertEqual(
            projected.get("workflow", {}).get("metadata", {}).get("current_phase"),
            expected_phase,
        )

    def test_tool_catalog_includes_default_c_workflow_tools(self):
        items = self.adapter.get_tool_catalog()
        names = set(item["name"] for item in items)

        self.assertIn("run_recipe", names)
        self.assertIn("task_status", names)
        self.assertIn("report_quality_v2", names)

    def test_tool_catalog_projects_dynamic_tools_only_when_shared_manager_allows_them(self):
        extension = FrontendCatalogDynamicToolExtension()
        self.adapter.extension_manager.register(extension)

        inactive = self.adapter.get_tool_catalog()
        extension.active = True
        active = self.adapter.get_tool_catalog()
        active_entry = [item for item in active if item.get("name") == "frontend_intranet_fetch"][0]

        self.assertFalse(any(item.get("name") == "frontend_intranet_fetch" for item in inactive))
        self.assertEqual(active_entry.get("source_id"), "frontend_catalog_dynamic")
        self.assertEqual(active_entry.get("source_type"), "extension")
        self.assertEqual(active_entry.get("permission_category"), "network")

    def test_capability_snapshot_keeps_registered_tool_names_and_counts(self):
        snapshot = self.adapter.capability_snapshot()
        names = [item.get("name") for item in snapshot.get("descriptors") or []]

        self.assertIn("read_file", names)
        self.assertIn("write_file", names)
        self.assertIsInstance(snapshot.get("counts"), dict)

    def test_session_capabilities_include_backend_declared_modes(self):
        capabilities = self.adapter.get_session_capabilities(self.snapshot["session_id"])
        modes = capabilities.get("modes") or []
        ids = [item.get("id") for item in modes]

        self.assertEqual(ids, ["build", "debug", "explore", "spec", "verify"])
        build = [item for item in modes if item.get("id") == "build"][0]
        self.assertEqual(build.get("dispatch"), {"kind": "mode.set", "mode": "build"})

    def test_session_snapshot_projector_is_side_effect_free(self):
        from embedagent.session_projector import SessionSnapshotProjector

        state = self.adapter._sessions[self.snapshot["session_id"]]
        before_messages = list(state.session.messages)
        runtime_lookup = getattr(self.tools, "runtime_environment_snapshot", None)
        runtime = runtime_lookup() if callable(runtime_lookup) else {}
        summary = self.adapter._read_summary_for_state(state)

        projected = SessionSnapshotProjector().build_snapshot(state, summary, runtime)

        self.assertEqual(before_messages, state.session.messages)
        self.assertEqual(projected["session_id"], self.snapshot["session_id"])
        self.assertIn("task_items", projected)
        self.assertIn("current_phase", projected)

    def test_adapter_reuses_one_engine_per_session(self):
        state = self.adapter._sessions[self.snapshot["session_id"]]
        first_engine = state.engine

        self.adapter.submit_user_message(self.snapshot["session_id"], "first turn", wait=True)
        self.adapter.submit_user_message(self.snapshot["session_id"], "second turn", wait=True)

        self.assertIs(state.engine, first_engine)

    def test_session_bootstrap_uses_history_without_timeline_api(self):
        self.adapter.submit_user_message(
            session_id=str(self.snapshot.get("session_id") or ""),
            text="hello",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: None,
        )
        payload = self.adapter.get_session_bootstrap(str(self.snapshot.get("session_id") or ""))
        self.assertIn("snapshot", payload)
        self.assertIn("history", payload)
        self.assertIn("permission_context", payload)
        self.assertNotIn("replay", payload)
        self.assertIn("activities", payload["history"])
        self.assertTrue(payload["history"]["activities"])
        self.assertEqual(payload["history"]["turns"][0]["steps"][0]["assistant_text"], "ok")

    def test_bootstrap_payload_is_assembled_by_service_contract(self):
        session_id = str(self.snapshot.get("session_id") or "")
        payload = self.adapter.get_session_bootstrap(session_id)

        self.assertEqual(payload["snapshot"]["session_id"], session_id)
        self.assertIn("history", payload)
        self.assertIn("plan", payload)
        self.assertIn("permission_context", payload)
        self.assertNotIn("replay", payload)

    def test_build_session_history_uses_active_session_state(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="读取文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        history = adapter.build_session_history(session_id)
        self.assertEqual(history["integrity"]["status"], "healthy")
        self.assertEqual(len(history["turns"]), 1)
        self.assertEqual(history["turns"][0]["user_text"], "读取文件")

    def test_build_session_history_marks_partial_restore_without_raw_fallback(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        session_id = "sess-partial-history"
        adapter.transcript_store.append_event(session_id, "session_meta", {"current_mode": "spec"})
        adapter.transcript_store.append_event(
            session_id,
            "message",
            {
                "role": "user",
                "content": "继续",
                "message_id": "m-user",
                "turn_id": "t-1",
                "step_id": "",
            },
        )
        adapter.transcript_store.append_event(
            session_id,
            "pending_interaction",
            {
                "turn_id": "t-1",
                "step_id": "",
                "kind": "user_input",
                "tool_name": "ask_user",
                "interaction_id": "pi-1",
                "request_payload": {"request": {"question": "继续吗？", "options": []}},
            },
        )
        adapter.transcript_store.append_event(
            session_id,
            "pending_resolution",
            {
                "turn_id": "t-1",
                "step_id": "",
                "interaction_id": "wrong-id",
                "kind": "user_input",
                "tool_name": "ask_user",
                "resolution_payload": {"answer": "继续"},
            },
        )
        history = adapter.build_session_history(session_id)
        self.assertEqual(history["integrity"]["status"], "partial")
        self.assertEqual(
            history["integrity"]["restore_stop_reason"], "pending_resolution_identity_mismatch"
        )
        self.assertTrue(history["turns"])
        self.assertEqual(history["history_source"], "transcript_restore")

    def test_session_history_splits_single_turn_into_multiple_agent_steps(self):
        adapter = InProcessAdapter(
            client=MultiStepClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="请分析这个文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        payload = adapter.build_session_history(session_id)
        self.assertEqual(len(payload["turns"]), 1)
        turn = payload["turns"][0]
        self.assertEqual(turn["user_text"], "请分析这个文件")
        self.assertEqual(len(turn["steps"]), 2)
        self.assertEqual(turn["steps"][0]["tool_calls"][0]["call_id"], "call-step-1")
        self.assertEqual(turn["steps"][0]["reasoning"], "先读取文件内容。")
        self.assertEqual(turn["steps"][1]["assistant_text"], "分析完成，文件结构正常。")
        self.assertEqual(turn["steps"][1]["reasoning"], "读取完成，总结结果。")
        step_ids = [step["step_id"] for step in turn["steps"]]
        self.assertEqual(len(step_ids), len(set(step_ids)))
        self.assertEqual(payload["history_source"], "session_state")
        self.assertEqual(payload["integrity"]["status"], "healthy")

    def test_session_history_never_returns_raw_event_projection(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="读取文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        history = adapter.build_session_history(session_id)
        self.assertIn(history["history_source"], ("session_state", "transcript_restore"))
        self.assertIn(history["integrity"]["status"], ("healthy", "partial", "unavailable"))

    def test_session_history_reports_unavailable_when_transcript_missing(self):
        history = self.adapter.build_session_history("sess-missing")
        self.assertEqual(history["integrity"]["status"], "unavailable")
        self.assertEqual(history["integrity"]["restore_stop_reason"], "transcript_missing")
        self.assertEqual(history["turns"], [])

    def test_session_snapshot_includes_runtime_environment_summary(self):
        snapshot = self.adapter.get_session_snapshot(str(self.snapshot.get("session_id") or ""))
        self.assertIn("runtime_source", snapshot)
        self.assertIn("bundled_tools_ready", snapshot)
        self.assertIn("fallback_warnings", snapshot)
        self.assertIn("runtime_environment", snapshot)
        self.assertIsInstance(snapshot["fallback_warnings"], list)

    def test_session_snapshot_includes_context_analysis_fields(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="读取文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        refreshed = adapter.get_session_snapshot(session_id)
        self.assertIn("context_analysis", refreshed)
        self.assertIn("context_usage", refreshed)
        self.assertIn("compact_boundary_count", refreshed)
        self.assertIsInstance(refreshed["context_analysis"], dict)
        self.assertIsInstance(refreshed["context_usage"], dict)

    def test_session_snapshot_includes_compaction_state(self):
        adapter = InProcessAdapter(
            client=CompactRetryClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        state = adapter._require_session(session_id)
        with state.lock:
            session = state.session
            for index in range(5):
                session.add_user_message("old user %s %s" % (index, "u" * 400))
                session.add_assistant_reply(
                    AssistantReply(
                        content="old assistant %s %s" % (index, "a" * 300),
                        actions=[],
                        finish_reason="stop",
                    )
                )
                session.add_observation(
                    Action("read_file", {"path": "src/pkg/demo.c"}, "read-old-%s" % index),
                    Observation(
                        "read_file",
                        True,
                        None,
                        {
                            "path": "src/pkg/demo.c",
                            "content": "int demo(void) {\n%s\n}\n" % ("x" * 1200),
                            "content_stored_path": ".embedagent/memory/sessions/%s/tool-results/demo-%s/content.txt"
                            % (session_id, index),
                        },
                    ),
                )
        adapter.submit_user_message(
            session_id=session_id,
            text="继续分析",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        refreshed = adapter.get_session_snapshot(session_id)

        self.assertIn("compaction_state", refreshed)
        self.assertEqual(refreshed["compaction_state"]["boundary_count"], 1)
        self.assertIn(
            "src/pkg/demo.c",
            refreshed["compaction_state"]["latest_boundary"]["file_activity"]["read_files"],
        )

    def test_context_compacted_live_event_ignores_reused_compacted_history_checkpoint(self):
        class Result(object):
            compacted = True
            pipeline_steps = ["compacted_history_checkpoint", "working_set", "prompt_render"]

        self.assertFalse(_should_emit_context_compacted(Result()))

    def test_context_compacted_live_event_allows_new_compaction_triggers(self):
        class Result(object):
            compacted = True
            pipeline_steps = ["auto_compact_threshold", "working_set", "prompt_render"]

        self.assertTrue(_should_emit_context_compacted(Result()))

    def test_resume_appends_recovery_marker_and_snapshot_projects_recovery_state(self):
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")

        resumed_adapter = InProcessAdapter(
            client=FakeClient(),
            tools=ToolRuntime(self.workspace),
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        resumed = resumed_adapter.resume_session(session_id, "build")
        events = resumed_adapter.transcript_store.load_events(session_id)
        recovery_events = [item for item in events if item.get("type") == "recovery_marker"]

        self.assertEqual(len(recovery_events), 1)
        self.assertEqual(recovery_events[0]["payload"]["status"], "clean")
        self.assertIn("recovery_state", resumed)
        self.assertEqual(resumed["recovery_state"]["marker_count"], 1)
        self.assertEqual(resumed["recovery_state"]["latest_marker"]["status"], "clean")
        self.assertEqual(resumed["recovery_state"]["latest_marker"]["reason"], "resume")

    def test_session_snapshot_includes_workspace_intelligence_projection(self):
        with open(os.path.join(self.workspace, "tags"), "w", encoding="utf-8") as handle:
            handle.write("!_TAG_FILE_FORMAT\t2\t/extended format/\n")
            handle.write('demo\tsrc/pkg/demo.c\t/^int main(void) {$/;"\tf\n')
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="读取文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        refreshed = adapter.get_session_snapshot(session_id)
        self.assertIn("workspace_intelligence", refreshed)
        self.assertIn("context_pipeline_steps", refreshed)
        self.assertIsInstance(refreshed["workspace_intelligence"], list)
        self.assertGreaterEqual(len(refreshed["workspace_intelligence"]), 1)

    def test_session_snapshot_projects_default_llsp_file_evidence(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent", "llsp"), exist_ok=True)
        with open(
            os.path.join(self.workspace, ".embedagent", "llsp", "evidence.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                {
                    "items": [
                        {
                            "path": "src/pkg/demo.c",
                            "symbol": "demo_symbol",
                            "kind": "function",
                            "priority": 70,
                        }
                    ]
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="读取文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        refreshed = adapter.get_session_snapshot(session_id)
        self.assertIn("workspace_intelligence", refreshed)
        rendered_sections = [
            item.get("content") or ""
            for item in refreshed["workspace_intelligence"]
            if isinstance(item, dict)
        ]
        self.assertTrue(any("demo_symbol" in item for item in rendered_sections))

    def test_session_snapshot_and_history_include_compact_retry_projection(self):
        adapter = InProcessAdapter(
            client=CompactRetryClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        events = []
        adapter.submit_user_message(
            session_id=session_id,
            text="继续分析",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: events.append(
                (event_name, payload)
            ),
        )
        refreshed = adapter.get_session_snapshot(session_id)
        self.assertIn("last_transition_reason", refreshed)
        self.assertIn("recent_transition_reasons", refreshed)
        self.assertIn("compact_retry_count", refreshed)
        self.assertEqual(refreshed["last_transition_reason"], "completed")
        self.assertIn("compact_retry", refreshed["recent_transition_reasons"])
        self.assertEqual(refreshed["compact_retry_count"], 1)
        history = adapter.build_session_history(session_id)
        turn = history["turns"][0]
        self.assertIn("compact_retry", [item.get("kind") for item in turn["transitions"]])
        bootstrap = adapter.get_session_bootstrap(session_id)
        self.assertNotIn("replay", bootstrap)
        self.assertIn("compact_retry", [item[0] for item in events])

    def test_session_snapshot_includes_last_transition_message(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            max_turns=1,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="读取文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        refreshed = adapter.get_session_snapshot(session_id)
        self.assertEqual(refreshed["last_transition_reason"], "max_turns")
        self.assertIn("last_transition_message", refreshed)
        self.assertTrue(str(refreshed["last_transition_message"] or "").strip())
        self.assertIn("recent_transitions", refreshed)
        self.assertGreaterEqual(len(refreshed["recent_transitions"]), 1)
        self.assertEqual(refreshed["recent_transitions"][-1].get("reason"), "max_turns")
        self.assertEqual(refreshed["recent_transitions"][-1].get("display_reason"), "max_turns")
        self.assertTrue(str(refreshed["recent_transitions"][-1].get("message") or "").strip())

    def test_snapshot_enriches_legacy_recent_transitions_with_display_reason(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            max_turns=1,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="读取文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        refreshed = adapter.get_session_snapshot(session_id)
        summary_path = adapter.summary_store.resolve_summary_path(
            str(refreshed.get("summary_ref") or session_id)
        )
        with open(summary_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        for item in payload.get("recent_transitions") or []:
            if isinstance(item, dict) and "display_reason" in item:
                del item["display_reason"]
        with open(summary_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        legacy = adapter.get_session_snapshot(session_id)
        self.assertEqual(legacy["last_transition_display_reason"], "max_turns")
        self.assertEqual(legacy["recent_transitions"][-1].get("display_reason"), "max_turns")

    def test_session_history_includes_compact_retry_transition(self):
        adapter = InProcessAdapter(
            client=CompactRetryClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="继续分析",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        payload = adapter.build_session_history(session_id)
        self.assertEqual(len(payload["turns"]), 1)
        turn = payload["turns"][0]
        self.assertIn("transitions", turn)
        self.assertIn("compact_retry", [item.get("kind") for item in turn["transitions"]])
        self.assertEqual(len(turn["steps"]), 1)
        step = turn["steps"][0]
        self.assertIn("transitions", step)
        self.assertIn("compact_retry", [item.get("kind") for item in step["transitions"]])

    def test_session_history_preserves_user_input_wait_transition(self):
        adapter = InProcessAdapter(
            client=AskUserClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("spec")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="请继续",
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        payload = adapter.build_session_history(session_id)
        self.assertEqual(len(payload["turns"]), 1)
        turn = payload["turns"][0]
        self.assertEqual(turn["status"], "waiting_user_input")
        self.assertIn(
            "user_input_required", [item.get("kind") for item in turn.get("transitions", [])]
        )
        waiting_transition = [
            item
            for item in turn.get("transitions", [])
            if item.get("kind") == "user_input_required"
        ][0]
        self.assertEqual(waiting_transition.get("display_reason"), "waiting_user_input")
        self.assertEqual(len(turn["steps"]), 1)
        step = turn["steps"][0]
        self.assertEqual(step["status"], "user_input_wait")
        self.assertIn(
            "user_input_required", [item.get("kind") for item in step.get("transitions", [])]
        )

    def test_snapshot_and_session_history_preserve_permission_wait_transition(self):
        adapter = InProcessAdapter(
            client=WriteThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="写文件",
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        refreshed = adapter.get_session_snapshot(session_id)
        self.assertEqual(refreshed["status"], "waiting_permission")
        self.assertEqual(refreshed["last_transition_reason"], "permission_wait")
        self.assertEqual(refreshed["last_transition_display_reason"], "waiting_permission")
        self.assertEqual(
            refreshed["recent_transitions"][-1].get("display_reason"), "waiting_permission"
        )
        payload = adapter.build_session_history(session_id)
        self.assertEqual(len(payload["turns"]), 1)
        turn = payload["turns"][0]
        self.assertEqual(turn["status"], "waiting_permission")
        self.assertIn(
            "permission_required", [item.get("kind") for item in turn.get("transitions", [])]
        )
        waiting_transition = [
            item
            for item in turn.get("transitions", [])
            if item.get("kind") == "permission_required"
        ][0]
        self.assertEqual(waiting_transition.get("display_reason"), "waiting_permission")
        self.assertEqual(len(turn["steps"]), 1)
        step = turn["steps"][0]
        self.assertEqual(step["status"], "permission_wait")
        self.assertIn(
            "permission_required", [item.get("kind") for item in step.get("transitions", [])]
        )
        self.assertIn("pending_interaction", refreshed)
        self.assertEqual(refreshed["pending_interaction"]["kind"], "permission")
        self.assertEqual(refreshed["pending_interaction"]["tool_name"], "write_file")

    def test_session_history_preserves_max_turns_transition(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            max_turns=1,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="读取文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        payload = adapter.build_session_history(session_id)
        self.assertEqual(len(payload["turns"]), 1)
        turn = payload["turns"][0]
        self.assertEqual(turn["status"], "max_turns")
        self.assertIn("max_turns", [item.get("kind") for item in turn.get("transitions", [])])
        self.assertEqual(len(turn["steps"]), 1)
        step = turn["steps"][0]
        self.assertEqual(step["status"], "max_turns")
        self.assertIn("max_turns", [item.get("kind") for item in step.get("transitions", [])])
        terminal = [
            item for item in turn.get("transitions", []) if item.get("kind") == "max_turns"
        ][0]
        self.assertTrue(str(terminal.get("message") or "").strip())

    def test_snapshot_and_session_history_preserve_guard_stop_transition(self):
        adapter = InProcessAdapter(
            client=GuardStopClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="重复修改不存在文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        refreshed = adapter.get_session_snapshot(session_id)
        self.assertEqual(refreshed["last_transition_reason"], "guard_stop")
        self.assertTrue(str(refreshed["last_transition_message"] or "").strip())
        self.assertEqual(refreshed["recent_transitions"][-1].get("reason"), "guard_stop")
        self.assertEqual(refreshed["recent_transitions"][-1].get("display_reason"), "guard")
        payload = adapter.build_session_history(session_id)
        self.assertEqual(len(payload["turns"]), 1)
        turn = payload["turns"][0]
        self.assertEqual(turn["status"], "guard_stop")
        self.assertIn("guard_stop", [item.get("kind") for item in turn.get("transitions", [])])
        terminal = [
            item for item in turn.get("transitions", []) if item.get("kind") == "guard_stop"
        ][0]
        self.assertEqual(terminal.get("display_reason"), "guard")
        self.assertTrue(str(terminal.get("message") or "").strip())
        self.assertEqual(len(turn["steps"]), 1)
        self.assertIn(
            "guard_stop", [item.get("kind") for item in turn["steps"][0].get("transitions", [])]
        )

    def test_session_finished_event_includes_blocked_outcome(self):
        adapter = InProcessAdapter(
            client=GuardStopClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        events = []
        adapter.submit_user_message(
            session_id=session_id,
            text="重复修改不存在文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: events.append(
                (event_name, payload)
            ),
        )

        finished = [payload for event_name, payload in events if event_name == "session_finished"]
        turn_end = [payload for event_name, payload in events if event_name == "turn_end"]
        self.assertEqual(len(finished), 1)
        self.assertEqual(len(turn_end), 1)
        for payload in (finished[0], turn_end[0]):
            self.assertEqual(payload["outcome"]["kind"], "blocked")
            self.assertEqual(payload["outcome"]["reason"], "guard_stop")
            self.assertEqual(payload["outcome"]["exit_code"], 2)
            self.assertFalse(payload["outcome"]["is_success"])

    def test_snapshot_exposes_turn_experience_after_progressive_writes(self):
        adapter = InProcessAdapter(
            client=ThreeFileWriteThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")

        adapter.submit_user_message(
            session_id=session_id,
            text="创建三个项目文件",
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )

        refreshed = adapter.get_session_snapshot(session_id)
        experience = refreshed["turn_experience"]
        self.assertEqual(experience["status"], "completed")
        self.assertEqual(
            experience["completed"],
            [
                {"kind": "file_created", "path": "README.md"},
                {"kind": "file_created", "path": "src/main.c"},
                {"kind": "file_created", "path": "tests/test_demo.py"},
            ],
        )
        self.assertEqual(
            experience["next_steps"],
            ["Run validation for the changed files."],
        )

    def test_snapshot_and_session_history_preserve_cancelled_transition(self):
        client = CancellableToolClient()
        adapter = InProcessAdapter(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="读取文件后取消",
            stream=False,
            wait=False,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        time.sleep(0.2)
        adapter.cancel_session(session_id)
        client.release.set()
        deadline = time.time() + 8.0
        refreshed = {}
        while time.time() < deadline:
            refreshed = adapter.get_session_snapshot(session_id)
            if str(refreshed.get("last_transition_reason") or "") == "aborted":
                break
            time.sleep(0.05)
        self.assertEqual(refreshed.get("last_transition_reason"), "aborted")
        self.assertEqual(refreshed.get("last_transition_display_reason"), "cancelled")
        self.assertTrue(str(refreshed.get("last_transition_message") or "").strip())
        self.assertEqual(refreshed["recent_transitions"][-1].get("display_reason"), "cancelled")
        payload = adapter.build_session_history(session_id)
        self.assertEqual(len(payload["turns"]), 1)
        turn = payload["turns"][0]
        self.assertEqual(turn["status"], "aborted")
        self.assertIn("aborted", [item.get("kind") for item in turn.get("transitions", [])])
        terminal = [item for item in turn.get("transitions", []) if item.get("kind") == "aborted"][
            0
        ]
        self.assertEqual(terminal.get("display_reason"), "cancelled")
        self.assertTrue(str(terminal.get("message") or "").strip())

    def test_cancel_session_does_not_mark_idle_before_worker_exits(self):
        client = CancellableToolClient()
        adapter = InProcessAdapter(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="读取文件后取消",
            stream=False,
            wait=False,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        time.sleep(0.05)
        cancelling = adapter.cancel_session(session_id)
        self.assertEqual(cancelling.get("status"), "running")
        client.release.set()
        deadline = time.time() + 3.0
        final_snapshot = {}
        while time.time() < deadline:
            final_snapshot = adapter.get_session_snapshot(session_id)
            if (
                final_snapshot.get("status") == "idle"
                and final_snapshot.get("last_transition_reason") == "aborted"
            ):
                break
            time.sleep(0.05)
        self.assertEqual(final_snapshot.get("status"), "idle")
        self.assertEqual(final_snapshot.get("last_transition_reason"), "aborted")

    def test_cancel_session_clears_waiting_user_input_interaction(self):
        adapter = InProcessAdapter(
            client=AskUserClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("spec")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="请继续",
            stream=False,
            wait=False,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        deadline = time.time() + 3.0
        waiting = {}
        while time.time() < deadline:
            waiting = adapter.get_session_snapshot(session_id)
            if waiting.get("status") == "waiting_user_input":
                break
            time.sleep(0.05)
        self.assertEqual(waiting.get("status"), "waiting_user_input")
        self.assertTrue(waiting.get("pending_interaction_valid"))

        cancelled = adapter.cancel_session(session_id)

        self.assertEqual(cancelled.get("status"), "idle")
        self.assertFalse(cancelled.get("pending_interaction_valid"))
        self.assertIsNone(cancelled.get("pending_interaction"))
        final_snapshot = adapter.get_session_snapshot(session_id)
        self.assertFalse(final_snapshot.get("pending_interaction_valid"))
        self.assertIsNone(final_snapshot.get("pending_interaction"))

    def test_cancel_session_clears_waiting_permission_interaction(self):
        adapter = InProcessAdapter(
            client=WriteThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="写文件",
            stream=False,
            wait=False,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        deadline = time.time() + 3.0
        waiting = {}
        while time.time() < deadline:
            waiting = adapter.get_session_snapshot(session_id)
            if waiting.get("status") == "waiting_permission":
                break
            time.sleep(0.05)
        self.assertEqual(waiting.get("status"), "waiting_permission")
        self.assertTrue(waiting.get("pending_interaction_valid"))

        cancelled = adapter.cancel_session(session_id)

        self.assertEqual(cancelled.get("status"), "idle")
        self.assertFalse(cancelled.get("pending_interaction_valid"))
        self.assertIsNone(cancelled.get("pending_interaction"))
        self.assertFalse(os.path.exists(os.path.join(self.workspace, "src", "generated_write.c")))

    def test_new_turn_after_waiting_permission_cancel_does_not_keep_stop_signal(self):
        adapter = InProcessAdapter(
            client=WriteThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="写文件",
            stream=False,
            wait=False,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        deadline = time.time() + 3.0
        waiting = {}
        while time.time() < deadline:
            waiting = adapter.get_session_snapshot(session_id)
            if waiting.get("status") == "waiting_permission":
                break
            time.sleep(0.05)
        self.assertEqual(waiting.get("status"), "waiting_permission")
        adapter.cancel_session(session_id)

        adapter.client = FakeClient()
        refreshed = adapter.submit_user_message(
            session_id=session_id,
            text="继续",
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )

        self.assertEqual(refreshed.get("status"), "idle")
        self.assertEqual(refreshed.get("last_transition_reason"), "completed")

    def test_workspace_recipe_api_detects_cmake(self):
        with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
        payload = self.adapter.list_workspace_recipes()
        recipe_ids = [item["id"] for item in payload["items"]]
        self.assertIn("cmake.build.default", recipe_ids)
        self.assertIn("cmake.test.default", recipe_ids)

    def test_resume_session_rebuilds_from_transcript_when_summary_is_missing(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="读取文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        summary_path = adapter.summary_store.resolve_summary_path(session_id)
        if os.path.isfile(summary_path):
            os.remove(summary_path)
        restored = adapter.resume_session(session_id, "build")
        self.assertEqual(restored["session_id"], session_id)
        self.assertEqual(restored["current_mode"], "build")
        self.assertEqual(restored["last_assistant_message"], "done")

    def test_resume_session_restores_waiting_permission_from_transcript(self):
        adapter = InProcessAdapter(
            client=WriteThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="写文件",
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        restored = adapter.resume_session(session_id, "build")
        self.assertEqual(restored["status"], "waiting_permission")
        pending = restored.get("pending_interaction") or {}
        self.assertTrue(restored["pending_interaction_valid"])
        self.assertEqual(pending.get("kind"), "permission")
        self.assertTrue(str(pending.get("interaction_id") or "").strip())
        self.assertNotIn("has_pending_permission", restored)
        self.assertNotIn("pending_permission", restored)

    def test_resume_session_exposes_restore_diagnostics_for_clean_replay(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="读取文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        summary_path = adapter.summary_store.resolve_summary_path(session_id)
        if os.path.isfile(summary_path):
            os.remove(summary_path)
        restored = adapter.resume_session(session_id, "build")
        self.assertEqual(restored["restore_stop_reason"], "")
        self.assertEqual(
            restored["restore_consumed_event_count"], restored["restore_transcript_event_count"]
        )
        self.assertGreater(restored["restore_transcript_event_count"], 0)

    def test_resume_session_projects_operation_diagnostics(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="读取文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        restored = adapter.resume_session(session_id, "build")

        diagnostics = restored.get("operation_diagnostics") or {}
        self.assertGreater(diagnostics.get("total_count"), 0)
        self.assertEqual(diagnostics.get("interrupted_count"), 0)
        self.assertGreaterEqual(diagnostics.get("finished_count"), 1)
        kinds = diagnostics.get("kinds") or {}
        self.assertIn("turn", kinds)
        self.assertIn("provider_request", kinds)
        self.assertIn("save_point", kinds)

    def test_live_session_snapshot_projects_operation_diagnostics(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="读取文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        refreshed = adapter.get_session_snapshot(session_id)

        diagnostics = refreshed.get("operation_diagnostics") or {}
        self.assertGreater(diagnostics.get("total_count"), 0)
        self.assertEqual(diagnostics.get("interrupted_count"), 0)
        self.assertIn("turn", diagnostics.get("kinds") or {})
        self.assertIn("provider_request", diagnostics.get("kinds") or {})

    def test_live_session_snapshot_keeps_unfinished_operation_active(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.transcript_store.append_event(
            session_id,
            "operation_started",
            {
                "operation_id": "provider:req-live",
                "kind": "provider_request",
                "turn_id": "turn-live",
                "step_id": "step-live",
                "retryable": True,
            },
            schema_version=2,
        )

        refreshed = adapter.get_session_snapshot(session_id)

        diagnostics = refreshed.get("operation_diagnostics") or {}
        self.assertEqual(diagnostics.get("started_count"), 1)
        self.assertEqual(diagnostics.get("interrupted_count"), 0)
        active = diagnostics.get("active") or []
        self.assertEqual(active[0].get("operation_id"), "provider:req-live")
        self.assertEqual(active[0].get("status"), "started")

    def test_permission_ticket_does_not_write_session_history_directly(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        state = adapter._require_session(session_id)
        state.session.add_user_message("run recipe", turn_id="turn-live")
        state.session.begin_step(step_id="step-live")
        request = PermissionRequest(
            tool_name="run_recipe",
            category="toolchain_exec",
            reason="需要执行 recipe",
            details={"recipe_id": "custom.build"},
        )

        ticket = adapter.interaction_service.create_permission_ticket(
            state,
            request,
            turn_id="turn-live",
            step_id="step-live",
            step_index=1,
        )

        self.assertTrue(ticket.permission_id)
        self.assertEqual(request.details.get("_interaction_id"), ticket.permission_id)
        self.assertIsNone(state.session.pending_interaction)
        payload = adapter.build_session_history(session_id)
        turn = payload["turns"][0]
        self.assertEqual(turn["status"], "completed")
        self.assertNotEqual(turn["steps"][0]["status"], "permission_wait")
        self.assertEqual(turn["transitions"], [])

    def test_resume_session_exposes_restore_diagnostics_for_truncated_replay(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        session_id = "sess-bad-resume"
        adapter.transcript_store.append_event(session_id, "session_meta", {"current_mode": "spec"})
        adapter.transcript_store.append_event(
            session_id,
            "message",
            {
                "role": "user",
                "content": "继续",
                "message_id": "m-user",
                "turn_id": "t-1",
                "step_id": "",
            },
        )
        adapter.transcript_store.append_event(
            session_id,
            "step_started",
            {"turn_id": "t-1", "step_id": "s-1", "step_index": 1},
        )
        adapter.transcript_store.append_event(
            session_id,
            "pending_interaction",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "kind": "user_input",
                "tool_name": "ask_user",
                "interaction_id": "pi-1",
                "request_payload": {"question": "下一步怎么做？"},
            },
        )
        adapter.transcript_store.append_event(
            session_id,
            "pending_resolution",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "interaction_id": "pi-other",
                "kind": "user_input",
                "tool_name": "ask_user",
                "resolution_payload": {"answer": "继续"},
            },
        )

        restored = adapter.resume_session(session_id, "spec")
        self.assertEqual(restored["status"], "waiting_user_input")
        self.assertEqual(restored["restore_stop_reason"], "pending_resolution_identity_mismatch")
        self.assertEqual(restored["restore_consumed_event_count"], 4)
        self.assertEqual(restored["restore_transcript_event_count"], 5)

    def test_new_turn_clears_restore_stop_reason_before_fresh_ask_user(self):
        adapter = InProcessAdapter(
            client=AskUserClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        session_id = "sess-expired-resume"
        adapter.transcript_store.append_event(session_id, "session_meta", {"current_mode": "spec"})
        adapter.transcript_store.append_event(
            session_id,
            "message",
            {
                "role": "user",
                "content": "继续",
                "message_id": "m-user",
                "turn_id": "t-1",
                "step_id": "",
            },
        )
        adapter.transcript_store.append_event(
            session_id,
            "step_started",
            {"turn_id": "t-1", "step_id": "s-1", "step_index": 1},
        )
        adapter.transcript_store.append_event(
            session_id,
            "pending_interaction",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "kind": "user_input",
                "tool_name": "ask_user",
                "interaction_id": "",
                "request_payload": {"question": "旧问题"},
            },
        )

        restored = adapter.resume_session(session_id, "spec")
        self.assertEqual(restored["restore_stop_reason"], "interaction_expired")

        adapter.submit_user_message(
            session_id=session_id,
            text="请继续",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            user_input_resolver=lambda ticket: {
                "answer": "切到 debug 模式继续排查",
                "selected_index": 1,
                "selected_mode": "debug",
                "selected_option_text": "切到 debug 模式继续排查",
            },
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        refreshed = adapter.get_session_snapshot(session_id)
        self.assertEqual(refreshed["restore_stop_reason"], "")

    def test_adapter_does_not_expose_timeline_event_reload_api(self):
        self.assertFalse(hasattr(self.adapter, "load_session_events_after"))

    def test_resume_session_requires_transcript(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="读取文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        transcript_path = adapter.summary_store.resolve_transcript_path(session_id)
        if os.path.isfile(transcript_path):
            os.remove(transcript_path)
        with self.assertRaises(ValueError):
            adapter.resume_session(session_id, "build")

    def test_cancel_session_emits_interrupted_tool_result_when_tool_started(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        events = []
        cancelled = {"done": False}

        def handle(event_name, current_session_id, payload):
            events.append((event_name, payload))
            if event_name == "tool_started" and not cancelled["done"]:
                cancelled["done"] = True
                adapter.cancel_session(session_id)

        adapter.submit_user_message(
            session_id=session_id,
            text="读取文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=handle,
        )
        final_snapshot = adapter.get_session_snapshot(session_id)
        self.assertEqual(final_snapshot.get("last_transition_reason"), "aborted")
        tool_finished = [
            payload for event_name, payload in events if event_name == "tool_finished"
        ][-1]
        self.assertFalse(tool_finished.get("success"))
        self.assertEqual((tool_finished.get("data") or {}).get("error_kind"), "interrupted")

    def test_slash_recipes_emits_recipe_summary(self):
        with open(os.path.join(self.workspace, "Makefile"), "w", encoding="utf-8") as handle:
            handle.write("all:\n\t@echo build\n")
        events = []
        self.adapter.submit_user_message(
            session_id=str(self.snapshot.get("session_id") or ""),
            text="/recipes",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append(
                (event_name, payload)
            ),
        )
        command_events = [
            payload for event_name, payload in events if event_name == "command_result"
        ]
        self.assertEqual(command_events[0].get("command_name"), "recipes")
        self.assertIn("Workspace Recipes", command_events[0].get("message") or "")
        recipe_ids = [item["id"] for item in command_events[0].get("data", {}).get("items", [])]
        self.assertIn("make.build.default", recipe_ids)

    def test_clear_command_uses_session_view_payload(self):
        emitted = []
        session_id = str(self.snapshot.get("session_id") or "")
        self.adapter.submit_user_message(
            session_id=session_id,
            text="/clear",
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: emitted.append(
                (event_name, current_session_id, payload)
            ),
        )
        command_payloads = [
            payload for event_name, _, payload in emitted if event_name == "command_result"
        ]

        self.assertTrue(command_payloads)
        self.assertEqual(command_payloads[-1]["data"], {"clear_session_view": True})

    def test_slash_commands_dispatch_through_hosted_command_service(self):
        session_id = str(self.snapshot.get("session_id") or "")
        self.assertIsInstance(self.adapter.command_service, HostedCommandService)
        seen = []
        original_dispatch = self.adapter.command_service.dispatch

        def record_dispatch(state, text, event_handler, permission_resolver):
            seen.append(text)
            return original_dispatch(state, text, event_handler, permission_resolver)

        self.adapter.command_service.dispatch = record_dispatch
        try:
            self.adapter.submit_user_message(
                session_id=session_id,
                text="/tasks",
                stream=False,
                wait=True,
            )
        finally:
            self.adapter.command_service.dispatch = original_dispatch

        self.assertEqual(seen, ["/tasks"])

    @unittest.skipIf(sys.platform != "win32", "Windows-only: requires cmd.exe")
    def test_slash_run_executes_recipe_and_emits_tool_events(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent"), exist_ok=True)
        with open(
            os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                '[{"id":"custom.build","tool_name":"run_recipe","recipe_action":"build","label":"Custom Build","command":"cmd /c echo build-ok","cwd":"."}]'
            )
        events = []
        self.adapter.submit_user_message(
            session_id=str(self.snapshot.get("session_id") or ""),
            text="/run custom.build",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append(
                (event_name, payload)
            ),
        )
        event_names = [event_name for event_name, _ in events]
        self.assertIn("tool_started", event_names)
        self.assertIn("tool_finished", event_names)
        self.assertIn("turn_start", event_names)
        self.assertIn("turn_end", event_names)
        turn_start = [payload for event_name, payload in events if event_name == "turn_start"][0]
        tool_started = [payload for event_name, payload in events if event_name == "tool_started"][
            0
        ]
        tool_finished = [
            payload for event_name, payload in events if event_name == "tool_finished"
        ][0]
        command_events = [
            payload for event_name, payload in events if event_name == "command_result"
        ]
        self.assertEqual(command_events[0].get("command_name"), "run")
        self.assertTrue(command_events[0].get("success"))
        self.assertEqual(command_events[0].get("data", {}).get("recipe_id"), "custom.build")
        self.assertEqual(command_events[0].get("turn_id"), turn_start.get("turn_id"))
        self.assertEqual(tool_started.get("turn_id"), turn_start.get("turn_id"))
        self.assertEqual(tool_finished.get("turn_id"), turn_start.get("turn_id"))
        self.assertTrue(str(tool_started.get("step_id") or "").strip())
        self.assertEqual(tool_finished.get("step_id"), tool_started.get("step_id"))
        turn_end = [payload for event_name, payload in events if event_name == "turn_end"][0]
        self.assertEqual(turn_end["outcome"]["kind"], "completed")
        self.assertEqual(turn_end["outcome"]["reason"], "completed")
        self.assertEqual(turn_end["outcome"]["exit_code"], 0)

    def test_slash_run_permission_wait_enters_session_history(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent"), exist_ok=True)
        with open(
            os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                '[{"id":"custom.build","tool_name":"run_recipe","recipe_action":"build","label":"Custom Build","command":"cmd /c echo build-ok","cwd":"."}]'
            )
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")

        worker = threading.Thread(
            target=adapter.submit_user_message,
            kwargs={
                "session_id": session_id,
                "text": "/run custom.build",
                "stream": False,
                "wait": True,
                "event_handler": lambda event_name, current_session_id, payload: None,
            },
        )
        worker.start()

        deadline = time.time() + 3.0
        waiting = adapter.get_session_snapshot(session_id)
        while time.time() < deadline:
            waiting = adapter.get_session_snapshot(session_id)
            if waiting.get("status") == "waiting_permission":
                break
            time.sleep(0.05)
        permission_id = str((waiting.get("pending_interaction") or {}).get("interaction_id") or "")
        try:
            self.assertEqual(waiting["status"], "waiting_permission")
            self.assertIn("pending_interaction", waiting)
            self.assertEqual(waiting["pending_interaction"]["kind"], "permission")
            self.assertTrue(str(waiting["pending_interaction"].get("step_id") or "").strip())
            payload = adapter.build_session_history(session_id)
            self.assertEqual(len(payload["turns"]), 1)
            turn = payload["turns"][0]
            self.assertEqual(turn["status"], "waiting_permission")
            self.assertIn(
                "permission_required", [item.get("kind") for item in turn.get("transitions", [])]
            )
            self.assertEqual(len(turn["steps"]), 1)
            step = turn["steps"][0]
            self.assertEqual(step["status"], "permission_wait")
            self.assertTrue(str(step.get("step_id") or "").strip())
        finally:
            if permission_id:
                adapter.respond_to_interaction(session_id, permission_id, {"decision": "accept"})
            else:
                adapter.cancel_session(session_id)
            worker.join(3.0)

    def test_slash_run_permission_snapshot_and_history_wait_are_atomic(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent"), exist_ok=True)
        with open(
            os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                '[{"id":"custom.build","tool_name":"run_recipe","recipe_action":"build","label":"Custom Build","command":"cmd /c echo build-ok","cwd":"."}]'
            )
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        worker = threading.Thread(
            target=adapter.submit_user_message,
            kwargs={
                "session_id": session_id,
                "text": "/run custom.build",
                "stream": False,
                "wait": True,
                "event_handler": lambda event_name, current_session_id, payload: None,
            },
        )
        worker.start()
        deadline = time.time() + 3.0
        waiting = adapter.get_session_snapshot(session_id)
        while time.time() < deadline:
            waiting = adapter.get_session_snapshot(session_id)
            if waiting.get("status") == "waiting_permission":
                break
            time.sleep(0.001)
        permission_id = str((waiting.get("pending_interaction") or {}).get("interaction_id") or "")
        try:
            self.assertEqual(waiting["status"], "waiting_permission")
            for _ in range(20):
                payload = adapter.build_session_history(session_id)
                turn = payload["turns"][0]
                self.assertEqual(turn["status"], "waiting_permission")
                self.assertTrue(turn.get("transitions"))
        finally:
            if permission_id:
                adapter.respond_to_interaction(session_id, permission_id, {"decision": "accept"})
            else:
                adapter.cancel_session(session_id)
            worker.join(3.0)

    def test_wait_for_command_resolution_does_not_return_running_snapshot(self):
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        snapshots = [
            {"status": "waiting_permission", "pending_interaction_valid": True},
            {"status": "running", "pending_interaction_valid": False},
            {
                "status": "idle",
                "pending_interaction_valid": False,
            },
        ]
        original_get_snapshot = adapter.get_session_snapshot
        calls = []

        def fake_get_session_snapshot(current_session_id):
            calls.append(current_session_id)
            if snapshots:
                return snapshots.pop(0)
            return {
                "status": "idle",
                "pending_interaction_valid": False,
            }

        adapter.get_session_snapshot = fake_get_session_snapshot
        try:
            resolved = adapter.interaction_service.wait_for_command_resolution(
                session_id, timeout_s=0.2
            )
        finally:
            adapter.get_session_snapshot = original_get_snapshot

        self.assertEqual(resolved["status"], "idle")
        self.assertGreaterEqual(len(calls), 3)

    def test_slash_run_passes_target_and_profile_to_recipe(self):
        with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
        os.makedirs(os.path.join(self.workspace, "build", "debug"))
        events = []
        self.adapter.submit_user_message(
            session_id=str(self.snapshot.get("session_id") or ""),
            text="/run cmake.build.default demo-app debug",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append(
                (event_name, payload)
            ),
        )
        tool_finish = [payload for event_name, payload in events if event_name == "tool_finished"][
            0
        ]
        self.assertEqual(tool_finish.get("data", {}).get("recipe_id"), "cmake.build.default")
        self.assertEqual(tool_finish.get("data", {}).get("target"), "demo-app")
        self.assertEqual(tool_finish.get("data", {}).get("profile"), "debug")

    def test_session_scoped_tasks_are_isolated(self):
        first_session_id = str(self.snapshot.get("session_id") or "")
        second = self.adapter.create_session("build")
        second_session_id = str(second.get("session_id") or "")
        # No harness state pre-generated on session creation
        self.assertEqual(self.adapter.list_tasks(session_id=first_session_id)["count"], 0)
        self.assertEqual(self.adapter.list_tasks(session_id=second_session_id)["count"], 0)
        # set_session_mode triggers harness refresh for the target session
        self.adapter.set_session_mode(second_session_id, "verify")
        self.assertEqual(self.adapter.list_tasks(session_id=first_session_id)["count"], 0)
        self.assertEqual(self.adapter.list_tasks(session_id=second_session_id)["count"], 3)

    def test_session_status_events_cover_running_and_idle(self):
        events = []
        self.adapter.submit_user_message(
            session_id=str(self.snapshot.get("session_id") or ""),
            text="hello",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append(
                (event_name, payload)
            ),
        )
        statuses = [
            item[1].get("session_snapshot", {}).get("status")
            for item in events
            if item[0] == "session_status"
        ]
        self.assertIn("running", statuses)
        self.assertIn("idle", statuses)

    def test_tool_call_id_is_stable_across_start_and_finish(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        events = []
        adapter.submit_user_message(
            session_id=str(snapshot.get("session_id") or ""),
            text="读取文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append(
                (event_name, payload)
            ),
        )
        tool_start = [payload for event_name, payload in events if event_name == "tool_started"][0]
        tool_finish = [payload for event_name, payload in events if event_name == "tool_finished"][
            0
        ]
        self.assertEqual(tool_start.get("call_id"), "call-read-demo")
        self.assertEqual(tool_finish.get("call_id"), "call-read-demo")
        self.assertEqual(tool_start.get("tool_label"), "Read File")
        self.assertEqual(tool_finish.get("permission_category"), "read")
        self.assertEqual(tool_start.get("progress_renderer_key"), "file")
        self.assertEqual(tool_finish.get("result_renderer_key"), "file")
        self.assertEqual(tool_finish.get("read_model_invalidations"), [])

    def test_adapter_step_events_use_engine_step_id(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        events = []
        adapter.submit_user_message(
            session_id=str(snapshot.get("session_id") or ""),
            text="读取文件",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append(
                (event_name, payload)
            ),
        )
        step_start = [payload for event_name, payload in events if event_name == "step_start"][0]
        tool_start = [payload for event_name, payload in events if event_name == "tool_started"][0]
        step_end = [payload for event_name, payload in events if event_name == "step_end"][0]
        session_state = adapter._sessions[str(snapshot.get("session_id") or "")].session
        engine_step_id = session_state.turns[-1].steps[0].step_id

        self.assertEqual(step_start.get("step_id"), engine_step_id)
        self.assertEqual(tool_start.get("step_id"), engine_step_id)
        self.assertEqual(step_end.get("step_id"), engine_step_id)

    def test_user_input_flow_can_change_mode(self):
        adapter = InProcessAdapter(
            client=AskUserClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("spec")
        events = []
        adapter.submit_user_message(
            session_id=str(snapshot.get("session_id") or ""),
            text="请继续",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            user_input_resolver=lambda ticket: {
                "answer": "切到 debug 模式继续排查",
                "selected_index": 1,
                "selected_mode": "debug",
                "selected_option_text": "切到 debug 模式继续排查",
            },
            event_handler=lambda event_name, session_id, payload: events.append(event_name),
        )
        final_snapshot = adapter.get_session_snapshot(str(snapshot.get("session_id") or ""))
        self.assertEqual(final_snapshot["current_mode"], "debug")
        self.assertIn("user_input_required", events)

    def test_respond_to_interaction_emits_ask_user_tool_finish_and_completes_pending(self):
        adapter = InProcessAdapter(
            client=AskUserClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("spec")
        session_id = str(snapshot.get("session_id") or "")
        events = []
        self.assertIsInstance(adapter.interaction_service, HostedInteractionService)
        adapter.event_handler = lambda event_name, current_session_id, payload: events.append(
            (event_name, payload)
        )

        adapter.submit_user_message(
            session_id=session_id,
            text="请继续",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: events.append(
                (event_name, payload)
            ),
        )
        waiting = adapter.get_session_snapshot(session_id)
        interaction_id = str((waiting.get("pending_interaction") or {}).get("interaction_id") or "")
        self.assertEqual(waiting["status"], "waiting_user_input")
        self.assertTrue(interaction_id)

        adapter.respond_to_interaction(
            session_id,
            interaction_id,
            {"answers": {"answer": "切到 debug 模式继续排查"}},
        )

        tool_finished = [
            payload
            for event_name, payload in events
            if event_name == "tool_finished" and payload.get("tool_name") == "ask_user"
        ]
        self.assertGreaterEqual(len(tool_finished), 1)
        self.assertEqual(tool_finished[-1].get("call_id"), "call-ask")
        self.assertEqual((tool_finished[-1].get("data") or {}).get("selected_mode"), "debug")

        final_snapshot = adapter.get_session_snapshot(session_id)
        self.assertEqual(final_snapshot["status"], "idle")
        self.assertFalse(final_snapshot["pending_interaction_valid"])
        self.assertEqual(final_snapshot["current_mode"], "debug")

    def test_live_user_input_pending_id_matches_session_pending_interaction(self):
        adapter = InProcessAdapter(
            client=AskUserClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("spec")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="请继续",
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )

        waiting = adapter.get_session_snapshot(session_id)
        snapshot_interaction = waiting.get("pending_interaction") or {}
        state = adapter._sessions[session_id]
        with state.lock:
            session_pending = state.session.pending_interaction

        self.assertEqual(waiting["status"], "waiting_user_input")
        self.assertIsNotNone(session_pending)
        self.assertEqual(session_pending.kind, "user_input")
        self.assertEqual(
            session_pending.interaction_id,
            snapshot_interaction.get("interaction_id"),
        )
        self.assertEqual(snapshot_interaction.get("kind"), "user_input")
        self.assertIn("questions", snapshot_interaction)
        self.assertEqual(snapshot_interaction["questions"][0]["id"], "answer")
        self.assertEqual(snapshot_interaction["questions"][0]["question"], "下一步怎么做？")
        self.assertEqual(
            snapshot_interaction["questions"][0]["options"][0]["label"],
            "切到 debug 模式继续排查",
        )
        self.assertEqual(snapshot_interaction["questions"][0]["multi_select"], False)

    def test_managed_session_has_one_hosted_pending_interaction_field(self):
        adapter = InProcessAdapter(
            client=AskUserClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("spec")
        session_id = str(snapshot.get("session_id") or "")

        adapter.submit_user_message(
            session_id=session_id,
            text="请继续",
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )

        state = adapter._sessions[session_id]
        with state.lock:
            self.assertIsNotNone(state.pending_interaction)
            self.assertFalse(hasattr(state, "pending_permission"))
            self.assertFalse(hasattr(state, "pending_user_input"))
            self.assertFalse(hasattr(state, "pending_result"))
            self.assertFalse(hasattr(state, "pending_user_event"))
            self.assertFalse(hasattr(state, "pending_user_response"))

    def test_adapter_interaction_response_delegates_to_hosted_service(self):
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        calls = []

        class FakeInteractionService(object):
            def respond_to_interaction(self, session_id, interaction_id, payload):
                calls.append((session_id, interaction_id, dict(payload)))
                return {"status": "resolved"}

        adapter.interaction_service = FakeInteractionService()

        result = adapter.respond_to_interaction(
            "sess-1",
            "interaction-1",
            {"decision": "accept"},
        )

        self.assertEqual(calls, [("sess-1", "interaction-1", {"decision": "accept"})])
        self.assertEqual(result, {"status": "resolved"})

    def test_permission_accept_decision_returns_resolved_snapshot_for_command_wait(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent"), exist_ok=True)
        with open(
            os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                '[{"id":"custom.build","tool_name":"run_recipe","recipe_action":"build","label":"Custom Build","command":"cmd /c echo build-ok","cwd":"."}]'
            )
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        worker = threading.Thread(
            target=adapter.submit_user_message,
            kwargs={
                "session_id": session_id,
                "text": "/run custom.build",
                "stream": False,
                "wait": True,
                "event_handler": lambda event_name, current_session_id, payload: None,
            },
        )
        worker.start()
        deadline = time.time() + 3.0
        waiting = adapter.get_session_snapshot(session_id)
        while time.time() < deadline:
            waiting = adapter.get_session_snapshot(session_id)
            if waiting.get("status") == "waiting_permission":
                break
            time.sleep(0.05)
        pending = waiting.get("pending_interaction") or {}
        self.assertEqual(pending.get("kind"), "permission")
        permission_id = str(pending.get("interaction_id") or "")
        self.assertTrue(permission_id)

        resolved = adapter.respond_to_interaction(
            session_id,
            permission_id,
            {"decision": "accept"},
        )

        worker.join(3.0)
        self.assertEqual(resolved["status"], "idle")
        self.assertFalse(resolved["pending_interaction_valid"])
        self.assertIsNone(resolved.get("pending_interaction"))
        self.assertNotIn("has_pending_permission", resolved)

    def test_permission_accept_for_session_remembers_backend_ticket_category(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent"), exist_ok=True)
        with open(
            os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                '[{"id":"custom.build","tool_name":"run_recipe","recipe_action":"build","label":"Custom Build","command":"cmd /c echo build-ok","cwd":"."}]'
            )
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        worker = threading.Thread(
            target=adapter.submit_user_message,
            kwargs={
                "session_id": session_id,
                "text": "/run custom.build",
                "stream": False,
                "wait": True,
                "event_handler": lambda event_name, current_session_id, payload: None,
            },
        )
        worker.start()
        deadline = time.time() + 3.0
        waiting = adapter.get_session_snapshot(session_id)
        while time.time() < deadline:
            waiting = adapter.get_session_snapshot(session_id)
            if waiting.get("status") == "waiting_permission":
                break
            time.sleep(0.05)
        pending = waiting.get("pending_interaction") or {}
        self.assertEqual(pending.get("kind"), "permission")
        self.assertEqual(pending.get("category"), "toolchain_exec")
        interaction_id = str(pending.get("interaction_id") or "")
        self.assertTrue(interaction_id)

        adapter.respond_to_interaction(session_id, interaction_id, {"decision": "acceptForSession"})
        worker.join(3.0)

        context = adapter.get_permission_context(session_id)
        self.assertIn("toolchain_exec", context.remembered_categories)

    def test_respond_to_interaction_rejects_legacy_payload_shape(self):
        adapter = InProcessAdapter(
            client=AskUserClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("spec")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="请继续",
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        waiting = adapter.get_session_snapshot(session_id)
        interaction_id = str((waiting.get("pending_interaction") or {}).get("interaction_id") or "")

        with self.assertRaises(ValueError) as raised:
            adapter.respond_to_interaction(
                session_id,
                interaction_id,
                {"response_kind": "answer", "answer": "legacy"},
            )
        self.assertIn("invalid_interaction_response", str(raised.exception))

    def test_respond_to_interaction_conflicts_when_another_pending_is_active(self):
        adapter = InProcessAdapter(
            client=AskUserClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("spec")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="请继续",
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )

        with self.assertRaises(ValueError) as raised:
            adapter.respond_to_interaction(
                session_id,
                "different-id",
                {"answers": {"answer": "x"}},
            )
        self.assertIn("interaction_conflict", str(raised.exception))

    def test_permission_cancel_decision_interrupts_pending_wait(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent"), exist_ok=True)
        with open(
            os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                '[{"id":"custom.build","tool_name":"run_recipe","recipe_action":"build","label":"Custom Build","command":"cmd /c echo build-ok","cwd":"."}]'
            )
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        worker = threading.Thread(
            target=adapter.submit_user_message,
            kwargs={
                "session_id": session_id,
                "text": "/run custom.build",
                "stream": False,
                "wait": True,
                "event_handler": lambda event_name, current_session_id, payload: None,
            },
        )
        worker.start()
        deadline = time.time() + 3.0
        waiting = adapter.get_session_snapshot(session_id)
        while time.time() < deadline:
            waiting = adapter.get_session_snapshot(session_id)
            if waiting.get("status") == "waiting_permission":
                break
            time.sleep(0.05)
        interaction_id = str((waiting.get("pending_interaction") or {}).get("interaction_id") or "")
        self.assertTrue(interaction_id)

        resolved = adapter.respond_to_interaction(
            session_id, interaction_id, {"decision": "cancel"}
        )

        worker.join(3.0)
        self.assertFalse(worker.is_alive())
        final_snapshot = adapter.get_session_snapshot(session_id)
        self.assertFalse(final_snapshot["pending_interaction_valid"])
        self.assertIsNone(final_snapshot.get("pending_interaction"))
        self.assertIn(resolved["status"], ("idle", "running"))

    def test_live_permission_pending_id_matches_session_pending_interaction(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent"), exist_ok=True)
        with open(
            os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                '[{"id":"custom.build","tool_name":"run_recipe","recipe_action":"build","label":"Custom Build","command":"cmd /c echo build-ok","cwd":"."}]'
            )
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        worker = threading.Thread(
            target=adapter.submit_user_message,
            kwargs={
                "session_id": session_id,
                "text": "/run custom.build",
                "stream": False,
                "wait": True,
                "event_handler": lambda event_name, current_session_id, payload: None,
            },
        )
        worker.start()
        deadline = time.time() + 3.0
        waiting = adapter.get_session_snapshot(session_id)
        while time.time() < deadline:
            waiting = adapter.get_session_snapshot(session_id)
            if waiting.get("status") == "waiting_permission":
                break
            time.sleep(0.05)
        snapshot_interaction = waiting.get("pending_interaction") or {}
        permission_id = str(snapshot_interaction.get("interaction_id") or "")
        state = adapter._sessions[session_id]
        with state.lock:
            session_pending = state.session.pending_interaction
        try:
            self.assertEqual(waiting["status"], "waiting_permission")
            self.assertIsNotNone(session_pending)
            self.assertEqual(session_pending.kind, "permission")
            self.assertEqual(session_pending.interaction_id, permission_id)
        finally:
            if permission_id:
                adapter.respond_to_interaction(session_id, permission_id, {"decision": "accept"})
            else:
                adapter.cancel_session(session_id)
            worker.join(3.0)

    def test_interaction_response_remember_allows_next_matching_permission_in_session(self):
        adapter = InProcessAdapter(
            client=TwoWriteThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        adapter.submit_user_message(
            session_id=session_id,
            text="写两个文件",
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        waiting = adapter.get_session_snapshot(session_id)
        pending = waiting.get("pending_interaction") or {}
        self.assertEqual(waiting["status"], "waiting_permission")
        self.assertEqual(pending.get("category"), "workspace_write")
        permission_id = str(pending.get("interaction_id") or "")
        self.assertTrue(permission_id)

        adapter.respond_to_interaction(
            session_id,
            permission_id,
            {"decision": "acceptForSession"},
        )
        final_snapshot = adapter.get_session_snapshot(session_id)

        self.assertEqual(final_snapshot["status"], "idle")
        self.assertFalse(final_snapshot["pending_interaction_valid"])
        self.assertTrue(os.path.isfile(os.path.join(self.workspace, "src", "first_write.c")))
        self.assertTrue(os.path.isfile(os.path.join(self.workspace, "src", "second_write.c")))
        context = adapter.get_permission_context(session_id)
        self.assertIn("workspace_write", context.remembered_categories)

    def test_unknown_mode_create_session_raises(self):
        adapter = InProcessAdapter(
            client=SwitchModeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        with self.assertRaises(ValueError):
            adapter.create_session("orchestra")

    def test_slash_help_emits_command_result(self):
        events = []
        self.adapter.submit_user_message(
            session_id=str(self.snapshot.get("session_id") or ""),
            text="/help",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append(
                (event_name, payload)
            ),
        )
        event_names = [event_name for event_name, _ in events]
        self.assertIn("turn_start", event_names)
        self.assertIn("turn_end", event_names)
        turn_start = [payload for event_name, payload in events if event_name == "turn_start"][0]
        turn_end = [payload for event_name, payload in events if event_name == "turn_end"][0]
        command_events = [
            payload for event_name, payload in events if event_name == "command_result"
        ]
        self.assertEqual(len(command_events), 1)
        self.assertEqual(command_events[0].get("command_name"), "help")
        self.assertIn("Slash Commands", command_events[0].get("message") or "")
        self.assertEqual(command_events[0].get("turn_id"), turn_start.get("turn_id"))
        self.assertEqual(turn_end.get("turn_id"), turn_start.get("turn_id"))
        self.assertEqual(turn_end["outcome"]["kind"], "completed")
        self.assertEqual(turn_end["outcome"]["reason"], "completed")
        self.assertEqual(turn_end["outcome"]["exit_code"], 0)

    def test_slash_help_command_result_persists_in_resumed_history(self):
        session_id = str(self.snapshot.get("session_id") or "")
        self.adapter.submit_user_message(
            session_id=session_id,
            text="/help",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: None,
        )

        reloaded = InProcessAdapter(
            client=FakeClient(),
            tools=ToolRuntime(self.workspace),
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        resumed = reloaded.resume_session(session_id, "build")
        payload = reloaded.build_session_history(str(resumed.get("session_id") or ""))

        self.assertEqual(len(payload["turns"]), 1)
        turn = payload["turns"][0]
        self.assertEqual(turn["status"], "completed")
        command_results = [
            item for item in turn.get("transitions", []) if item.get("kind") == "command_result"
        ]
        self.assertEqual(len(command_results), 1)
        self.assertEqual(command_results[0].get("metadata", {}).get("command_name"), "help")
        self.assertIn("Slash Commands", command_results[0].get("message") or "")

    def test_slash_plan_persists_plan_snapshot(self):
        session_id = str(self.snapshot.get("session_id") or "")
        self.adapter.submit_user_message(
            session_id=session_id,
            text="/plan ## Summary\n\n- add tests",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: None,
        )
        snapshot = self.adapter.get_session_snapshot(session_id)
        self.assertTrue(snapshot["has_active_plan"])
        self.assertEqual(snapshot["workflow_state"], "plan")
        plan = self.adapter.get_session_plan(session_id)
        self.assertIsNotNone(plan)
        self.assertIn("add tests", plan.content)

    def test_slash_permissions_reflects_session_memory(self):
        session_id = str(self.snapshot.get("session_id") or "")
        self.adapter.remember_permission_category(session_id, "workspace_write")
        context = self.adapter.get_permission_context(session_id)
        self.assertIn("workspace_write", context.remembered_categories)

    def test_tool_catalog_exposes_renderer_metadata(self):
        items = self.adapter.get_tool_catalog()
        self.assertTrue(any(item.get("name") == "read_file" for item in items))
        self.assertFalse(any(item.get("name") == "compile_project" for item in items))
        read_file = [item for item in items if item.get("name") == "read_file"][0]
        task_status = [item for item in items if item.get("name") == "task_status"][0]
        self.assertEqual(read_file.get("user_label"), "Read File")
        self.assertEqual(read_file.get("result_renderer_key"), "file")
        self.assertEqual(task_status.get("progress_renderer_key"), "tasks")
        self.assertEqual(task_status.get("result_renderer_key"), "tasks")
        self.assertEqual(task_status.get("activity_kind"), "task")

    def test_slash_review_emits_structured_findings(self):
        session_id = str(self.snapshot.get("session_id") or "")
        state = self.adapter._sessions[session_id]
        action = Action("run_recipe", {"recipe_id": "cmake.build.default"}, "call-build-1")
        state.session.add_user_message("build failed", turn_id="turn-review-build")
        state.session.begin_step(step_id="step-review-build")
        state.session.record_tool_call(action)
        state.session.add_observation(
            action,
            Observation(
                "run_recipe",
                False,
                "命令退出码为 1。",
                {
                    "recipe_id": "cmake.build.default",
                    "recipe_action": "build",
                    "diagnostics": [
                        {
                            "file": "src/pkg/demo.c",
                            "line": 2,
                            "column": 5,
                            "message": "expected ';' after return statement",
                        }
                    ],
                },
            ),
        )
        events = []
        self.adapter.submit_user_message(
            session_id=session_id,
            text="/review",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append(
                (event_name, payload)
            ),
        )
        command_events = [
            payload for event_name, payload in events if event_name == "command_result"
        ]
        self.assertEqual(command_events[0].get("command_name"), "review")
        review = command_events[0].get("data", {}).get("review", {})
        findings = review.get("findings") or []
        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "high")
        self.assertIn("Build failed", findings[0]["title"])
        sections = review.get("sections") or {}
        self.assertGreaterEqual(len(sections.get("diagnostics") or []), 1)
        git_sections = sections.get("git") or []
        self.assertGreaterEqual(len(git_sections), 1)
        self.assertIn("diff_preview", git_sections[0])
        self.assertIn("diff_stored_path", git_sections[0])
        self.assertNotIn("diff_artifact_ref", git_sections[0])

    def test_slash_review_emits_findings_from_official_verify_path(self):
        session_id = str(self.snapshot.get("session_id") or "")
        state = self.adapter._sessions[session_id]
        state.session.add_user_message("verify failed", turn_id="turn-review-verify")
        state.session.begin_step(step_id="step-review-verify")
        test_action = Action("run_recipe", {"recipe_id": "cmake.test.default"}, "call-run-verify-1")
        state.session.record_tool_call(test_action)
        state.session.add_observation(
            test_action,
            Observation(
                "run_recipe",
                False,
                "recipe failed",
                {
                    "recipe_id": "cmake.test.default",
                    "recipe_action": "test",
                    "test_summary": {"failed": 1, "passed": 0, "total": 1},
                    "diagnostics": [
                        {
                            "file": "src/pkg/demo.c",
                            "line": 2,
                            "column": 5,
                            "message": "expected ';' after return statement",
                        }
                    ],
                    "error_count": 1,
                    "warning_count": 0,
                },
            ),
        )
        quality_action = Action("report_quality_v2", {}, "call-quality-verify-1")
        state.session.record_tool_call(quality_action)
        state.session.add_observation(
            quality_action,
            Observation(
                "report_quality_v2",
                True,
                None,
                {
                    "passed": False,
                    "error_count": 1,
                    "warning_count": 0,
                    "test_failures": 1,
                    "reasons": ["quality failed"],
                },
            ),
        )
        events = []
        self.adapter.submit_user_message(
            session_id=session_id,
            text="/review",
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append(
                (event_name, payload)
            ),
        )
        command_events = [
            payload for event_name, payload in events if event_name == "command_result"
        ]
        review = command_events[0].get("data", {}).get("review", {})
        findings = review.get("findings") or []
        self.assertGreaterEqual(len(findings), 1)
        self.assertTrue(review.get("verify_evidence_present"))
        self.assertTrue(review.get("tests_seen"))
        titles = [str(item.get("title") or "") for item in findings]
        bodies = [str(item.get("body") or "") for item in findings]
        self.assertTrue(
            any("Tests failing" in title or "Quality gate failed" in title for title in titles)
        )
        self.assertFalse(any("`run_tests`" in body for body in bodies))


if __name__ == "__main__":
    unittest.main()
