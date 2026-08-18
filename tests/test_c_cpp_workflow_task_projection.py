import os
import shutil
import sys
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent_runtime_test_helpers import cpp_application_registry
from embedagent_core.permissions import PermissionPolicy
from embedagent_host.inprocess_adapter import InProcessAdapter
from embedagent_host.runtime.tools import ToolRuntime
from embedagent_workflow_cpp import task_store

_COUNTER = count(1)


def _make_workspace(name):
    root = os.path.join(
        os.path.dirname(__file__),
        "..",
        "build",
        "test-sandboxes",
        "%s-%s-%s" % (name, os.getpid(), next(_COUNTER)),
    )
    root = os.path.realpath(root)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    return root


class DoneClient(object):
    def generate(self, messages, tools=None):
        from embedagent_core.session import AssistantReply

        del messages, tools
        return AssistantReply(content="done", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        if on_reasoning_delta is not None and reply.reasoning_content:
            on_reasoning_delta(reply.reasoning_content)
        return reply


class HarnessTaskProjectionTests(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("task-projection")
        self.tools = ToolRuntime(self.workspace)
        self.adapter = InProcessAdapter(
            client=DoneClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            agent_application_registry=cpp_application_registry(),
        )

    def tearDown(self):
        self.adapter.shutdown()
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_build_session_projects_harness_tasks_without_legacy_todo_store(self):
        snapshot = self.adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        state = self.adapter._sessions[session_id]

        # Before explicit work request: no tasks
        payload = self.adapter.list_tasks(session_id=session_id)
        self.assertEqual(payload["count"], 0)

        # Submit explicit work request to trigger harness
        self.adapter.submit_user_message(
            session_id=session_id,
            text="build the project",
            stream=False,
            wait=True,
        )

        payload = self.adapter.list_tasks(session_id=session_id)

        self.assertGreaterEqual(payload["count"], 1)
        self.assertEqual(
            payload["path"],
            ".embedagent/memory/sessions/%s/task-graph.json" % session_id,
        )
        workflow = (state.projection.get("workflow_state") or {}).get("workflow") or {}
        self.assertEqual(len(workflow.get("items") or []), payload["count"])
        self.assertTrue(os.path.isfile(task_store.task_snapshot_path(self.workspace, session_id)))
        stored = task_store.load_task_snapshot(self.workspace, session_id)
        self.assertEqual(stored["snapshot_schema_version"], 2)
        self.assertTrue(stored["source_workflow_fingerprint"])
        self.assertFalse(
            os.path.exists(
                os.path.join(
                    self.workspace,
                    ".embedagent",
                    "memory",
                    "sessions",
                    session_id,
                    "to" + "dos.json",
                )
            )
        )

    def test_restart_and_corrupt_sidecar_use_canonical_session_projection(self):
        snapshot = self.adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        self.adapter.submit_user_message(
            session_id=session_id,
            text="build the project",
            stream=False,
            wait=True,
        )
        self.adapter.shutdown()

        with open(task_store.task_snapshot_path(self.workspace, session_id), "w") as handle:
            handle.write("not-json")

        restarted = InProcessAdapter(
            client=DoneClient(),
            tools=ToolRuntime(self.workspace),
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
            agent_application_registry=cpp_application_registry(),
        )
        try:
            payload = restarted.list_tasks(session_id=session_id)
            self.assertGreaterEqual(payload["count"], 1)
            self.assertEqual(payload["session_id"], session_id)
        finally:
            restarted.shutdown()

    def test_mode_change_does_not_synthesize_task_track_without_explicit_work(self):
        snapshot = self.adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")

        self.adapter.set_session_mode(session_id, "verify")
        payload = self.adapter.list_tasks(session_id=session_id)
        state = self.adapter._sessions[session_id]

        self.assertEqual(payload["tasks"], [])
        self.assertEqual((state.projection.get("workflow_state") or {}).get("workflow"), None)


if __name__ == "__main__":
    unittest.main()
