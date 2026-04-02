import os
import shutil
import sys
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from embedagent.session_timeline import SessionTimelineStore


_COUNTER = count(1)


def _make_workspace():
    root = os.path.join(
        os.path.dirname(__file__),
        "..",
        "build",
        "test-sandboxes",
        "timeline-%s" % next(_COUNTER),
    )
    root = os.path.realpath(root)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    return root


class TestSessionTimelineStore(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace()
        self.store = SessionTimelineStore(self.workspace, max_events=3)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_append_and_load_events(self):
        self.store.append_event('sess-1', 'turn_started', {'text': 'hello'})
        self.store.append_event('sess-1', 'tool_started', {'tool_name': 'read_file'})
        events = self.store.load_events('sess-1')
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]['event'], 'turn_started')
        self.assertEqual(events[1]['event'], 'tool_started')

    def test_latest_assistant_reply_comes_from_session_finished(self):
        self.store.append_event('sess-2', 'turn_started', {'text': 'hi'})
        self.store.append_event('sess-2', 'session_finished', {'final_text': 'done'})
        self.assertEqual(self.store.latest_assistant_reply('sess-2'), 'done')

    def test_assistant_delta_is_not_persisted(self):
        self.store.append_event('sess-3', 'assistant_delta', {'text': 'partial'})
        self.assertEqual(self.store.load_events('sess-3'), [])

    def test_max_events_trim(self):
        for index in range(5):
            self.store.append_event('sess-4', 'turn_started', {'text': 'msg-%s' % index})
        events = self.store.load_events('sess-4', limit=10)
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]['payload']['text'], 'msg-2')


if __name__ == '__main__':
    unittest.main()
