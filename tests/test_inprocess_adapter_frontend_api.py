import json
import os
import shutil
import sys
import threading
import time
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from embedagent.inprocess_adapter import InProcessAdapter
from embedagent.llm import ModelClientError
from embedagent.permissions import PermissionPolicy
from embedagent.session import Action, AssistantReply
from embedagent.transcript_store import TranscriptStore
from embedagent.tools import ToolRuntime


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
    def generate(self, messages, tools=None):
        return AssistantReply(content='ok', actions=[], finish_reason='stop')

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
                        arguments={"target": "code", "reason": "规格已明确，开始实现。"},
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
        return AssistantReply(content='after compact', actions=[], finish_reason='stop')

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
                        arguments={"path": "notes/out.md", "content": "# hi\n", "overwrite": True},
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
        os.makedirs(os.path.join(self.workspace, 'src', 'pkg'))
        with open(os.path.join(self.workspace, 'src', 'pkg', 'demo.c'), 'w', encoding='utf-8') as handle:
            handle.write('int main(void) {\n    return 0;\n}\n')
        os.makedirs(os.path.join(self.workspace, '.embedagent'))
        with open(os.path.join(self.workspace, '.embedagent', 'todos.json'), 'w', encoding='utf-8') as handle:
            json.dump([{'id': 1, 'content': 'demo', 'done': False}], handle)
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
            tool_name="run_command",
            field_name="stdout",
            stored_path=stored.relative_path,
            preview_text=stored.preview_text,
            byte_count=stored.byte_count,
            line_count=stored.line_count,
            content_kind=stored.content_kind,
            created_at="2026-04-05T00:00:00Z",
        )
        self.snapshot = self.adapter.create_session('code')

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_workspace_snapshot_and_tree(self):
        payload = self.adapter.get_workspace_snapshot()
        self.assertEqual(payload['workspace'], os.path.realpath(self.workspace))
        tree = self.adapter.list_workspace_tree(path='src', max_depth=2, limit=20)
        paths = [item['path'] for item in tree['items']]
        self.assertIn('src/pkg', paths)
        self.assertIn('src/pkg/demo.c', paths)
        children = self.adapter.list_workspace_children(path='src', limit=20)
        pkg = [item for item in children['items'] if item['path'] == 'src/pkg'][0]
        self.assertTrue(pkg['has_children'])

    def test_read_and_write_workspace_file(self):
        loaded = self.adapter.read_workspace_file('src/pkg/demo.c')
        self.assertIn('return 0;', loaded['content'])
        result = self.adapter.write_workspace_file('src/pkg/demo.c', 'int main(void) {\n    return 1;\n}\n')
        self.assertIn('diff_preview', result)
        reloaded = self.adapter.read_workspace_file('src/pkg/demo.c')
        self.assertIn('return 1;', reloaded['content'])

    def test_artifact_and_todo_apis(self):
        artifacts = self.adapter.list_artifacts(limit=10)
        self.assertGreaterEqual(len(artifacts), 1)
        payload = self.adapter.read_artifact(artifacts[0]['path'])
        self.assertEqual(payload['kind'], 'text')
        todos = self.adapter.list_todos()
        self.assertEqual(todos['count'], 1)

    def test_timeline_api(self):
        events = []
        self.adapter.submit_user_message(
            session_id=str(self.snapshot.get('session_id') or ''),
            text='hello',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append(event_name),
        )
        payload = self.adapter.get_session_timeline(str(self.snapshot.get('session_id') or ''))
        self.assertTrue(any(item['event'] == 'turn_started' for item in payload['events']))
        self.assertEqual(payload['latest_assistant_reply'], 'ok')

    def test_structured_timeline_splits_single_turn_into_multiple_agent_steps(self):
        adapter = InProcessAdapter(
            client=MultiStepClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='请分析这个文件',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        payload = adapter.build_structured_timeline(session_id)
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
        self.assertEqual(payload["projection_source"], "step_events")
        self.assertEqual(turn["projection_kind"], "step_events")
        self.assertTrue(all(not step.get("synthetic") for step in turn["steps"]))
        self.assertTrue(all(step.get("projection_kind") == "recorded_step" for step in turn["steps"]))

    def test_structured_timeline_marks_turn_level_projection_as_synthetic_step(self):
        snapshot = self.adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        self.adapter.timeline_store.append_event(
            session_id,
            "turn_start",
            {"turn_id": "turn-legacy", "user_text": "legacy turn"},
        )
        self.adapter.timeline_store.append_event(
            session_id,
            "reasoning_delta",
            {"turn_id": "turn-legacy", "text": "legacy reasoning"},
        )
        self.adapter.timeline_store.append_event(
            session_id,
            "tool_started",
            {"turn_id": "turn-legacy", "call_id": "call-legacy", "tool_name": "read_file", "arguments": {"path": "src/pkg/demo.c"}},
        )
        self.adapter.timeline_store.append_event(
            session_id,
            "tool_finished",
            {"turn_id": "turn-legacy", "call_id": "call-legacy", "tool_name": "read_file", "success": True, "data": {"path": "src/pkg/demo.c"}},
        )
        self.adapter.timeline_store.append_event(
            session_id,
            "turn_end",
            {"turn_id": "turn-legacy", "termination_reason": "completed", "final_text": "legacy done"},
        )
        payload = self.adapter.build_structured_timeline(session_id)
        self.assertEqual(payload["projection_source"], "turn_events")
        self.assertEqual(len(payload["turns"]), 1)
        turn = payload["turns"][0]
        self.assertEqual(turn["projection_kind"], "turn_events")
        self.assertEqual(len(turn["steps"]), 1)
        step = turn["steps"][0]
        self.assertTrue(step["synthetic"])
        self.assertEqual(step["projection_kind"], "synthetic_single_step")
        self.assertEqual(step["assistant_text"], "legacy done")
        self.assertEqual(step["reasoning"], "legacy reasoning")

    def test_structured_timeline_reports_raw_event_projection_without_turns(self):
        snapshot = self.adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        self.adapter.timeline_store.append_event(
            session_id,
            "tool_started",
            {"call_id": "call-raw", "tool_name": "read_file", "arguments": {"path": "src/pkg/demo.c"}},
        )
        payload = self.adapter.build_structured_timeline(session_id)
        self.assertEqual(payload["projection_source"], "raw_events")
        self.assertEqual(payload["turns"], [])
        self.assertTrue(any(item.get("event") == "tool_started" for item in payload["events"]))

    def test_session_snapshot_includes_runtime_environment_summary(self):
        snapshot = self.adapter.get_session_snapshot(str(self.snapshot.get('session_id') or ''))
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
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='读取文件',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        refreshed = adapter.get_session_snapshot(session_id)
        self.assertIn("context_analysis", refreshed)
        self.assertIn("compact_boundary_count", refreshed)
        self.assertIsInstance(refreshed["context_analysis"], dict)

    def test_session_snapshot_includes_workspace_intelligence_projection(self):
        with open(os.path.join(self.workspace, "tags"), "w", encoding="utf-8") as handle:
            handle.write("!_TAG_FILE_FORMAT\t2\t/extended format/\n")
            handle.write("demo\tsrc/pkg/demo.c\t/^int main(void) {$/;\"\tf\n")
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='读取文件',
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
        with open(os.path.join(self.workspace, ".embedagent", "llsp", "evidence.json"), "w", encoding="utf-8") as handle:
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
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='读取文件',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        refreshed = adapter.get_session_snapshot(session_id)
        self.assertIn("workspace_intelligence", refreshed)
        rendered_sections = [item.get("content") or "" for item in refreshed["workspace_intelligence"] if isinstance(item, dict)]
        self.assertTrue(any("demo_symbol" in item for item in rendered_sections))

    def test_session_snapshot_and_timeline_include_compact_retry_projection(self):
        adapter = InProcessAdapter(
            client=CompactRetryClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        events = []
        adapter.submit_user_message(
            session_id=session_id,
            text='继续分析',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: events.append((event_name, payload)),
        )
        refreshed = adapter.get_session_snapshot(session_id)
        self.assertIn("last_transition_reason", refreshed)
        self.assertIn("recent_transition_reasons", refreshed)
        self.assertIn("compact_retry_count", refreshed)
        self.assertEqual(refreshed["last_transition_reason"], "completed")
        self.assertIn("compact_retry", refreshed["recent_transition_reasons"])
        self.assertEqual(refreshed["compact_retry_count"], 1)
        timeline = adapter.get_session_timeline(session_id)
        self.assertTrue(any(item["event"] == "compact_retry" for item in timeline["events"]))
        self.assertIn("compact_retry", [item[0] for item in events])

    def test_session_snapshot_includes_last_transition_message(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            max_turns=1,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='读取文件',
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
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='读取文件',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        refreshed = adapter.get_session_snapshot(session_id)
        summary_path = adapter.summary_store.resolve_summary_path(str(refreshed.get("summary_ref") or session_id))
        with open(summary_path, 'r', encoding='utf-8') as handle:
            payload = json.load(handle)
        for item in payload.get("recent_transitions") or []:
            if isinstance(item, dict) and "display_reason" in item:
                del item["display_reason"]
        with open(summary_path, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        legacy = adapter.get_session_snapshot(session_id)
        self.assertEqual(legacy["last_transition_display_reason"], "max_turns")
        self.assertEqual(legacy["recent_transitions"][-1].get("display_reason"), "max_turns")

    def test_structured_timeline_includes_compact_retry_transition(self):
        adapter = InProcessAdapter(
            client=CompactRetryClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='继续分析',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        payload = adapter.build_structured_timeline(session_id)
        self.assertEqual(len(payload["turns"]), 1)
        turn = payload["turns"][0]
        self.assertIn("transitions", turn)
        self.assertIn("compact_retry", [item.get("kind") for item in turn["transitions"]])
        self.assertEqual(len(turn["steps"]), 1)
        step = turn["steps"][0]
        self.assertIn("transitions", step)
        self.assertIn("compact_retry", [item.get("kind") for item in step["transitions"]])

    def test_structured_timeline_preserves_user_input_wait_transition(self):
        adapter = InProcessAdapter(
            client=AskUserClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session('spec')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='请继续',
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        payload = adapter.build_structured_timeline(session_id)
        self.assertEqual(len(payload["turns"]), 1)
        turn = payload["turns"][0]
        self.assertEqual(turn["status"], "waiting_user_input")
        self.assertIn("user_input_required", [item.get("kind") for item in turn.get("transitions", [])])
        waiting_transition = [item for item in turn.get("transitions", []) if item.get("kind") == "user_input_required"][0]
        self.assertEqual(waiting_transition.get("display_reason"), "waiting_user_input")
        self.assertEqual(len(turn["steps"]), 1)
        step = turn["steps"][0]
        self.assertEqual(step["status"], "user_input_wait")
        self.assertIn("user_input_required", [item.get("kind") for item in step.get("transitions", [])])

    def test_snapshot_and_structured_timeline_preserve_permission_wait_transition(self):
        adapter = InProcessAdapter(
            client=WriteThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='写文件',
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        refreshed = adapter.get_session_snapshot(session_id)
        self.assertEqual(refreshed["status"], "waiting_permission")
        self.assertEqual(refreshed["last_transition_reason"], "permission_wait")
        self.assertEqual(refreshed["last_transition_display_reason"], "waiting_permission")
        self.assertEqual(refreshed["recent_transitions"][-1].get("display_reason"), "waiting_permission")
        payload = adapter.build_structured_timeline(session_id)
        self.assertEqual(len(payload["turns"]), 1)
        turn = payload["turns"][0]
        self.assertEqual(turn["status"], "waiting_permission")
        self.assertIn("permission_required", [item.get("kind") for item in turn.get("transitions", [])])
        waiting_transition = [item for item in turn.get("transitions", []) if item.get("kind") == "permission_required"][0]
        self.assertEqual(waiting_transition.get("display_reason"), "waiting_permission")
        self.assertEqual(len(turn["steps"]), 1)
        step = turn["steps"][0]
        self.assertEqual(step["status"], "permission_wait")
        self.assertIn("permission_required", [item.get("kind") for item in step.get("transitions", [])])
        self.assertIn("pending_interaction", refreshed)
        self.assertEqual(refreshed["pending_interaction"]["kind"], "permission")
        self.assertEqual(refreshed["pending_interaction"]["tool_name"], "write_file")

    def test_structured_timeline_preserves_max_turns_transition(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            max_turns=1,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='读取文件',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        payload = adapter.build_structured_timeline(session_id)
        self.assertEqual(len(payload["turns"]), 1)
        turn = payload["turns"][0]
        self.assertEqual(turn["status"], "max_turns")
        self.assertIn("max_turns", [item.get("kind") for item in turn.get("transitions", [])])
        self.assertEqual(len(turn["steps"]), 1)
        step = turn["steps"][0]
        self.assertEqual(step["status"], "max_turns")
        self.assertIn("max_turns", [item.get("kind") for item in step.get("transitions", [])])
        terminal = [item for item in turn.get("transitions", []) if item.get("kind") == "max_turns"][0]
        self.assertTrue(str(terminal.get("message") or "").strip())

    def test_snapshot_and_structured_timeline_preserve_guard_stop_transition(self):
        adapter = InProcessAdapter(
            client=GuardStopClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='重复修改不存在文件',
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
        payload = adapter.build_structured_timeline(session_id)
        self.assertEqual(len(payload["turns"]), 1)
        turn = payload["turns"][0]
        self.assertEqual(turn["status"], "guard_stop")
        self.assertIn("guard_stop", [item.get("kind") for item in turn.get("transitions", [])])
        terminal = [item for item in turn.get("transitions", []) if item.get("kind") == "guard_stop"][0]
        self.assertEqual(terminal.get("display_reason"), "guard")
        self.assertTrue(str(terminal.get("message") or "").strip())
        self.assertEqual(len(turn["steps"]), 1)
        self.assertIn("guard_stop", [item.get("kind") for item in turn["steps"][0].get("transitions", [])])

    def test_snapshot_and_structured_timeline_preserve_cancelled_transition(self):
        client = CancellableToolClient()
        adapter = InProcessAdapter(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='读取文件后取消',
            stream=False,
            wait=False,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        time.sleep(0.05)
        adapter.cancel_session(session_id)
        client.release.set()
        deadline = time.time() + 3.0
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
        payload = adapter.build_structured_timeline(session_id)
        self.assertEqual(len(payload["turns"]), 1)
        turn = payload["turns"][0]
        self.assertEqual(turn["status"], "aborted")
        self.assertIn("aborted", [item.get("kind") for item in turn.get("transitions", [])])
        terminal = [item for item in turn.get("transitions", []) if item.get("kind") == "aborted"][0]
        self.assertEqual(terminal.get("display_reason"), "cancelled")
        self.assertTrue(str(terminal.get("message") or "").strip())

    def test_cancel_session_does_not_mark_idle_before_worker_exits(self):
        client = CancellableToolClient()
        adapter = InProcessAdapter(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='读取文件后取消',
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
            if final_snapshot.get("status") == "idle" and final_snapshot.get("last_transition_reason") == "aborted":
                break
            time.sleep(0.05)
        self.assertEqual(final_snapshot.get("status"), "idle")
        self.assertEqual(final_snapshot.get("last_transition_reason"), "aborted")

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
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='读取文件',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        summary_path = adapter.summary_store.resolve_summary_path(session_id)
        if os.path.isfile(summary_path):
            os.remove(summary_path)
        restored = adapter.resume_session(session_id, 'code')
        self.assertEqual(restored["session_id"], session_id)
        self.assertEqual(restored["current_mode"], "code")
        self.assertEqual(restored["last_assistant_message"], "done")

    def test_resume_session_restores_waiting_permission_from_transcript(self):
        adapter = InProcessAdapter(
            client=WriteThenDoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
        )
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='写文件',
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        restored = adapter.resume_session(session_id, 'code')
        self.assertEqual(restored["status"], "waiting_permission")
        self.assertTrue(restored["has_pending_permission"])

    def test_resume_session_exposes_restore_diagnostics_for_clean_replay(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='读取文件',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        summary_path = adapter.summary_store.resolve_summary_path(session_id)
        if os.path.isfile(summary_path):
            os.remove(summary_path)
        restored = adapter.resume_session(session_id, 'code')
        self.assertEqual(restored["restore_stop_reason"], "")
        self.assertEqual(restored["restore_consumed_event_count"], restored["restore_transcript_event_count"])
        self.assertGreater(restored["restore_transcript_event_count"], 0)

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
            {"role": "user", "content": "继续", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
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

        restored = adapter.resume_session(session_id, 'spec')
        self.assertEqual(restored["status"], "waiting_user_input")
        self.assertEqual(restored["restore_stop_reason"], "pending_resolution_identity_mismatch")
        self.assertEqual(restored["restore_consumed_event_count"], 4)
        self.assertEqual(restored["restore_transcript_event_count"], 5)

    def test_load_session_events_after_returns_reload_required_when_after_seq_falls_before_retained_window(self):
        self.adapter.timeline_store.max_events = 3
        session_id = str(self.snapshot.get('session_id') or '')
        for index in range(5):
            self.adapter.timeline_store.append_event(
                session_id,
                'tool_started',
                {'tool_name': 'read_file', 'call_id': 'call-%s' % index},
            )
        self.adapter.timeline_store._trim_if_needed(self.adapter.timeline_store._timeline_path(session_id))
        payload = self.adapter.load_session_events_after(session_id, after_seq=1, limit=50)
        self.assertEqual(payload["status"], "reload_required")
        self.assertGreater(payload["first_seq"], 1)

    def test_resume_session_requires_transcript(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='读取文件',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        transcript_path = adapter.summary_store.resolve_transcript_path(session_id)
        if os.path.isfile(transcript_path):
            os.remove(transcript_path)
        with self.assertRaises(ValueError):
            adapter.resume_session(session_id, 'code')

    def test_cancel_session_emits_interrupted_tool_result_when_tool_started(self):
        adapter = InProcessAdapter(
            client=ToolClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        events = []
        cancelled = {"done": False}

        def handle(event_name, current_session_id, payload):
            events.append((event_name, payload))
            if event_name == "tool_started" and not cancelled["done"]:
                cancelled["done"] = True
                adapter.cancel_session(session_id)

        adapter.submit_user_message(
            session_id=session_id,
            text='读取文件',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=handle,
        )
        final_snapshot = adapter.get_session_snapshot(session_id)
        self.assertEqual(final_snapshot.get("last_transition_reason"), "aborted")
        tool_finished = [payload for event_name, payload in events if event_name == "tool_finished"][-1]
        self.assertFalse(tool_finished.get("success"))
        self.assertEqual((tool_finished.get("data") or {}).get("error_kind"), "interrupted")

    def test_slash_recipes_emits_recipe_summary(self):
        with open(os.path.join(self.workspace, "Makefile"), "w", encoding="utf-8") as handle:
            handle.write("all:\n\t@echo build\n")
        events = []
        self.adapter.submit_user_message(
            session_id=str(self.snapshot.get('session_id') or ''),
            text='/recipes',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append((event_name, payload)),
        )
        command_events = [payload for event_name, payload in events if event_name == "command_result"]
        self.assertEqual(command_events[0].get("command_name"), "recipes")
        self.assertIn("Workspace Recipes", command_events[0].get("message") or "")
        recipe_ids = [item["id"] for item in command_events[0].get("data", {}).get("items", [])]
        self.assertIn("make.build.default", recipe_ids)

    def test_slash_run_executes_recipe_and_emits_tool_events(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent"), exist_ok=True)
        with open(os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"), "w", encoding="utf-8") as handle:
            handle.write(
                '[{"id":"custom.build","tool_name":"compile_project","label":"Custom Build","command":"cmd /c echo build-ok","cwd":"."}]'
            )
        events = []
        self.adapter.submit_user_message(
            session_id=str(self.snapshot.get('session_id') or ''),
            text='/run custom.build',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append((event_name, payload)),
        )
        event_names = [event_name for event_name, _ in events]
        self.assertIn("tool_started", event_names)
        self.assertIn("tool_finished", event_names)
        self.assertIn("turn_start", event_names)
        self.assertIn("turn_end", event_names)
        turn_start = [payload for event_name, payload in events if event_name == "turn_start"][0]
        tool_started = [payload for event_name, payload in events if event_name == "tool_started"][0]
        tool_finished = [payload for event_name, payload in events if event_name == "tool_finished"][0]
        command_events = [payload for event_name, payload in events if event_name == "command_result"]
        self.assertEqual(command_events[0].get("command_name"), "run")
        self.assertTrue(command_events[0].get("success"))
        self.assertEqual(command_events[0].get("data", {}).get("recipe_id"), "custom.build")
        self.assertEqual(command_events[0].get("turn_id"), turn_start.get("turn_id"))
        self.assertEqual(tool_started.get("turn_id"), turn_start.get("turn_id"))
        self.assertEqual(tool_finished.get("turn_id"), turn_start.get("turn_id"))
        self.assertEqual(tool_started.get("step_id"), "")
        self.assertEqual(tool_finished.get("step_id"), "")

    def test_slash_run_passes_target_and_profile_to_recipe(self):
        with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
        events = []
        self.adapter.submit_user_message(
            session_id=str(self.snapshot.get('session_id') or ''),
            text='/run cmake.build.default demo-app debug',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append((event_name, payload)),
        )
        tool_finish = [payload for event_name, payload in events if event_name == "tool_finished"][0]
        self.assertEqual(tool_finish.get("data", {}).get("recipe_id"), "cmake.build.default")
        self.assertEqual(tool_finish.get("data", {}).get("target"), "demo-app")
        self.assertEqual(tool_finish.get("data", {}).get("profile"), "debug")

    def test_session_scoped_todos_are_isolated(self):
        first_session_id = str(self.snapshot.get('session_id') or '')
        self.tools.execute("manage_todos", {"action": "add", "content": "session-one", "session_id": first_session_id})
        second = self.adapter.create_session('code')
        second_session_id = str(second.get('session_id') or '')
        self.assertEqual(self.adapter.list_todos(session_id=first_session_id)["count"], 1)
        self.assertEqual(self.adapter.list_todos(session_id=second_session_id)["count"], 0)

    def test_session_status_events_cover_running_and_idle(self):
        events = []
        self.adapter.submit_user_message(
            session_id=str(self.snapshot.get('session_id') or ''),
            text='hello',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append((event_name, payload)),
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
        snapshot = adapter.create_session('code')
        events = []
        adapter.submit_user_message(
            session_id=str(snapshot.get('session_id') or ''),
            text='读取文件',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append((event_name, payload)),
        )
        tool_start = [payload for event_name, payload in events if event_name == "tool_started"][0]
        tool_finish = [payload for event_name, payload in events if event_name == "tool_finished"][0]
        self.assertEqual(tool_start.get("call_id"), "call-read-demo")
        self.assertEqual(tool_finish.get("call_id"), "call-read-demo")
        self.assertEqual(tool_start.get("tool_label"), "Read File")
        self.assertEqual(tool_finish.get("permission_category"), "read")
        self.assertEqual(tool_start.get("progress_renderer_key"), "file")
        self.assertEqual(tool_finish.get("result_renderer_key"), "file")

    def test_user_input_flow_can_change_mode(self):
        adapter = InProcessAdapter(
            client=AskUserClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session('spec')
        events = []
        adapter.submit_user_message(
            session_id=str(snapshot.get('session_id') or ''),
            text='请继续',
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
        final_snapshot = adapter.get_session_snapshot(str(snapshot.get('session_id') or ''))
        self.assertEqual(final_snapshot["current_mode"], "debug")
        self.assertIn("user_input_required", events)

    def test_explore_mode_with_switch_mode_intent(self):
        """Test that explore mode (fallback for removed orchestra) handles switch_mode intent.
        
        Note: switch_mode tool is no longer available in any mode; mode switching is
        now user-driven via /mode command or ask_user options.
        """
        adapter = InProcessAdapter(
            client=SwitchModeClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        # orchestra mode no longer exists, falls back to explore
        snapshot = adapter.create_session('orchestra')
        # Initial mode should be fallback (explore)
        initial_snapshot = adapter.get_session_snapshot(str(snapshot.get('session_id') or ''))
        self.assertEqual(initial_snapshot["current_mode"], "explore")
        adapter.submit_user_message(
            session_id=str(snapshot.get('session_id') or ''),
            text='安排下一步',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: None,
        )
        # Mode should remain explore (no switch_mode tool available)
        final_snapshot = adapter.get_session_snapshot(str(snapshot.get('session_id') or ''))
        self.assertEqual(final_snapshot["current_mode"], "explore")

    def test_slash_help_emits_command_result(self):
        events = []
        self.adapter.submit_user_message(
            session_id=str(self.snapshot.get('session_id') or ''),
            text='/help',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append((event_name, payload)),
        )
        event_names = [event_name for event_name, _ in events]
        self.assertIn("turn_start", event_names)
        self.assertIn("turn_end", event_names)
        turn_start = [payload for event_name, payload in events if event_name == "turn_start"][0]
        turn_end = [payload for event_name, payload in events if event_name == "turn_end"][0]
        command_events = [payload for event_name, payload in events if event_name == "command_result"]
        self.assertEqual(len(command_events), 1)
        self.assertEqual(command_events[0].get("command_name"), "help")
        self.assertIn("Slash Commands", command_events[0].get("message") or "")
        self.assertEqual(command_events[0].get("turn_id"), turn_start.get("turn_id"))
        self.assertEqual(turn_end.get("turn_id"), turn_start.get("turn_id"))

    def test_slash_plan_persists_plan_snapshot(self):
        session_id = str(self.snapshot.get('session_id') or '')
        self.adapter.submit_user_message(
            session_id=session_id,
            text='/plan ## Summary\n\n- add tests',
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
        session_id = str(self.snapshot.get('session_id') or '')
        self.adapter.remember_permission_category(session_id, "workspace_write")
        context = self.adapter.get_permission_context(session_id)
        self.assertIn("workspace_write", context.remembered_categories)

    def test_tool_catalog_exposes_renderer_metadata(self):
        items = self.adapter.get_tool_catalog()
        self.assertTrue(any(item.get("name") == "read_file" for item in items))
        read_file = [item for item in items if item.get("name") == "read_file"][0]
        self.assertEqual(read_file.get("user_label"), "Read File")
        self.assertEqual(read_file.get("result_renderer_key"), "file")

    def test_slash_review_emits_structured_findings(self):
        session_id = str(self.snapshot.get('session_id') or '')
        self.adapter.timeline_store.append_event(
            session_id,
            "tool_finished",
            {
                "tool_name": "compile_project",
                "success": False,
                "call_id": "call-build-1",
                "error": "命令退出码为 1。",
                "data": {
                    "diagnostics": [
                        {
                            "file": "src/pkg/demo.c",
                            "line": 2,
                            "column": 5,
                            "message": "expected ';' after return statement",
                        }
                    ]
                },
            },
        )
        events = []
        self.adapter.submit_user_message(
            session_id=session_id,
            text='/review',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append((event_name, payload)),
        )
        command_events = [payload for event_name, payload in events if event_name == "command_result"]
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


if __name__ == '__main__':
    unittest.main()
