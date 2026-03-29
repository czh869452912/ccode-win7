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

    def stream(self, messages, tools=None, on_text_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None:
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


if __name__ == '__main__':
    unittest.main()
