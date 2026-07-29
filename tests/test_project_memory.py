import json
import os
import shutil
import sys
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_core.session import Action, AssistantReply, Observation, Session
from embedagent_core.session_view import session_read_view
from embedagent_host.runtime import project_memory
from embedagent_host.runtime.project_memory import ProjectMemoryStore, _atomic_write_json


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

    def test_atomic_write_json_retries_transient_permission_error(self):
        path = os.path.join(self.workspace, ".embedagent", "memory", "project", "state.json")
        attempts = []
        real_replace = project_memory.os.replace

        def flaky_replace(src, dst):
            attempts.append((src, dst))
            if len(attempts) < 3:
                raise PermissionError("locked")
            return real_replace(src, dst)

        with mock.patch(
            "embedagent_host.runtime.project_memory.os.replace", side_effect=flaky_replace
        ):
            _atomic_write_json(path, {"ok": True})

        self.assertEqual(len(attempts), 3)
        with open(path, "r", encoding="utf-8") as handle:
            self.assertIn('"ok": true', handle.read())
        parent = os.path.dirname(path)
        leftovers = [name for name in os.listdir(parent) if name.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_refresh_records_recipe_evidence_by_payload_shape_not_tool_name(self):
        store = ProjectMemoryStore(self.workspace)
        session = Session(session_id="memory-custom-recipe")
        session.add_user_message("build")
        action = Action(
            "custom_build_runner",
            {"command": "custom build", "cwd": "."},
            "call-custom-build",
        )
        session.add_assistant_reply(
            AssistantReply(content="", actions=[action], finish_reason="tool_calls")
        )
        session.add_observation(
            action,
            Observation(
                "custom_build_runner",
                True,
                None,
                {
                    "command": "custom build",
                    "cwd": ".",
                    "recipe_action": "build",
                },
            ),
        )

        store.refresh(session_read_view(session), "build")

        with open(store.recipes_path, "r", encoding="utf-8") as handle:
            recipes = json.load(handle)
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]["tool_name"], "custom_build_runner")
        self.assertEqual(recipes[0]["recipe_action"], "build")


if __name__ == "__main__":
    unittest.main()
