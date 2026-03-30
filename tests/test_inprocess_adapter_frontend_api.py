import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from embedagent.inprocess_adapter import InProcessAdapter
from embedagent.permissions import PermissionPolicy
from embedagent.session import Action, AssistantReply
from embedagent.tools import ToolRuntime


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


class TestInProcessAdapterFrontendApis(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()
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
        self.tools.artifact_store.write_text('run_command', 'stdout', 'hello artifact')
        self.snapshot = self.adapter.create_session('code')

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


if __name__ == '__main__':
    unittest.main()
