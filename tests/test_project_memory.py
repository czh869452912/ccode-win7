import os
import shutil
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.project_memory import ProjectMemoryStore


class ProjectMemoryStoreConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.workspace = os.path.realpath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "build",
                "test-sandboxes",
                "project-memory-%s" % os.getpid(),
            )
        )
        shutil.rmtree(self.workspace, ignore_errors=True)
        os.makedirs(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_read_paths_wait_for_store_lock(self):
        store = ProjectMemoryStore(self.workspace)
        store.cleanup()

        started = threading.Event()
        finished = threading.Event()
        result = []

        def reader():
            started.set()
            result.append(store.build_system_message("build", 600))
            finished.set()

        with store._lock:
            thread = threading.Thread(target=reader)
            thread.start()
            self.assertTrue(started.wait(1.0))
            time.sleep(0.05)
            self.assertFalse(finished.is_set())

        thread.join(1.0)
        self.assertTrue(finished.is_set())
        self.assertEqual(result, [None])


if __name__ == "__main__":
    unittest.main()
