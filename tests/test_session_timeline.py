import os
import shutil
import sys
import threading
import time
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

    def test_append_event_keeps_seq_monotonic(self):
        first = self.store.append_event('sess-5', 'turn_started', {'text': 'hello'})
        second = self.store.append_event('sess-5', 'tool_started', {'tool_name': 'read_file'})
        self.assertEqual(first['seq'], 1)
        self.assertEqual(second['seq'], 2)

    def test_append_event_serializes_concurrent_writers(self):
        self.store.append_event('sess-6', 'turn_started', {'text': 'hello'})
        original_next_seq = self.store._next_seq
        first_seq_started = threading.Event()
        first_call_seen = [False]

        def delayed_next_seq(path):
            seq = original_next_seq(path)
            if not first_call_seen[0]:
                first_call_seen[0] = True
                first_seq_started.set()
                time.sleep(0.2)
            return seq

        self.store._next_seq = delayed_next_seq
        errors = []

        def writer(index):
            try:
                self.store.append_event('sess-6', 'tool_started', {'tool_name': 'read_file', 'index': index})
            except Exception as exc:
                errors.append(exc)

        thread_a = threading.Thread(target=writer, args=(1,))
        thread_b = threading.Thread(target=writer, args=(2,))
        thread_a.start()
        self.assertTrue(first_seq_started.wait(1.0))
        thread_b.start()
        thread_a.join()
        thread_b.join()

        self.assertEqual(errors, [])
        events = self.store.load_events('sess-6', limit=10)
        self.assertEqual([item['seq'] for item in events], [1, 2, 3])
        self.assertEqual(events[-2]['payload']['index'], 1)
        self.assertEqual(events[-1]['payload']['index'], 2)


if __name__ == '__main__':
    unittest.main()
