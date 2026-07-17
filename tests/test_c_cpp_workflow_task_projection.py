import os
import shutil
import sys
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_core.permissions import PermissionPolicy
from embedagent_host.inprocess_adapter import InProcessAdapter
from embedagent_host.runtime.tools import ToolRuntime
from embedagent_workflow_cpp import task_store

from embedagent.agent_application_registry import product_agent_application_registry

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
            agent_application_registry=product_agent_application_registry(),
        )

    def tearDown(self):
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
            permission_resolver=lambda ticket: True,
        )

        payload = self.adapter.list_tasks(session_id=session_id)

        self.assertGreaterEqual(payload["count"], 1)
        self.assertEqual(
            payload["path"],
            ".embedagent/memory/sessions/%s/task-graph.json" % session_id,
        )
        workflow = state.session.workflow_state.get("workflow") or {}
        self.assertEqual(len(workflow.get("items") or []), payload["count"])
        self.assertTrue(os.path.isfile(task_store.task_snapshot_path(self.workspace, session_id)))
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

    def test_mode_change_refreshes_projected_task_track(self):
        snapshot = self.adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")

        self.adapter.set_session_mode(session_id, "verify")
        payload = self.adapter.list_tasks(session_id=session_id)
        state = self.adapter._sessions[session_id]

        self.assertEqual(
            [item["content"] for item in payload["tasks"]],
            [
                "verify:select_recipe",
                "verify:execute",
                "verify:summarize",
            ],
        )
        self.assertEqual(
            [item["content"] for item in state.session.workflow_state["workflow"]["items"]],
            [item["content"] for item in payload["tasks"]],
        )


if __name__ == "__main__":
    unittest.main()
