import json
import os
import shutil
import sys
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.extensions import ResourcesDiscoverResult
from embedagent.inprocess_adapter import InProcessAdapter
from embedagent.permissions import PermissionPolicy
from embedagent.session import AssistantReply
from embedagent.tools import ToolRuntime

_COUNTER = count(1)


def _make_workspace(prefix):
    root = os.path.join(
        os.path.dirname(__file__),
        "..",
        "build",
        "test-sandboxes",
        "%s-%s" % (prefix, next(_COUNTER)),
    )
    root = os.path.realpath(root)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    return root


def _write_text(path, content):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


class FakeClient(object):
    def generate(self, messages, tools=None):
        del messages, tools
        return AssistantReply(content="ok", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None:
            on_text_delta(reply.content)
        return reply


class ExtraResourceExtension(object):
    extension_id = "extra_resources"
    builtin_extension = False

    def __init__(self, recipe_path):
        self.recipe_path = recipe_path

    def resources_discover(self, event, context):
        assert event.reason
        assert context.workspace
        return ResourcesDiscoverResult(
            recipe_paths=[self.recipe_path],
            metadata={"extension": self.extension_id},
        )


class TestLocalResources(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("local-resources")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_discovers_default_skill_prompt_and_recipe_files(self):
        from embedagent.local_resources import discover_local_resources

        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "review.md"),
            "# Review Skill\n",
        )
        _write_text(
            os.path.join(self.workspace, ".embedagent", "prompts", "triage.md"),
            "# Triage Prompt\n",
        )
        _write_text(
            os.path.join(self.workspace, ".embedagent", "recipes", "build.json"),
            json.dumps(
                {
                    "id": "local.build",
                    "tool_name": "run_recipe",
                    "recipe_action": "build",
                    "label": "Local Build",
                    "command": "cmd /c echo build-ok",
                    "cwd": ".",
                }
            ),
        )

        payload = discover_local_resources(self.workspace)

        self.assertEqual(payload["counts"]["skills"], 1)
        self.assertEqual(payload["counts"]["prompts"], 1)
        self.assertEqual(payload["counts"]["recipes"], 1)
        self.assertEqual(payload["skills"][0]["path"], ".embedagent/skills/review.md")
        self.assertEqual(payload["prompts"][0]["path"], ".embedagent/prompts/triage.md")
        self.assertEqual(payload["recipes"][0]["id"], "local.build")
        self.assertEqual(payload["recipes"][0]["source"], "local_resource")
        self.assertEqual(payload["diagnostics"], [])

    def test_recipe_file_diagnostics_do_not_block_other_resources(self):
        from embedagent.local_resources import discover_local_resources

        _write_text(
            os.path.join(self.workspace, ".embedagent", "recipes", "bad.json"),
            "{not-json",
        )
        _write_text(
            os.path.join(self.workspace, ".embedagent", "recipes", "ok.json"),
            json.dumps(
                {
                    "id": "local.test",
                    "tool_name": "run_recipe",
                    "recipe_action": "test",
                    "label": "Local Test",
                    "command": "cmd /c echo test-ok",
                }
            ),
        )

        payload = discover_local_resources(self.workspace)

        self.assertEqual(payload["counts"]["recipes"], 1)
        self.assertEqual(payload["recipes"][0]["id"], "local.test")
        self.assertEqual(len(payload["diagnostics"]), 1)
        self.assertEqual(payload["diagnostics"][0]["kind"], "recipe")
        self.assertIn("bad.json", payload["diagnostics"][0]["path"])

    def test_workspace_recipes_include_local_resource_recipes(self):
        _write_text(
            os.path.join(self.workspace, ".embedagent", "recipes", "build.json"),
            json.dumps(
                {
                    "id": "local.build",
                    "tool_name": "run_recipe",
                    "recipe_action": "build",
                    "label": "Local Build",
                    "command": "cmd /c echo build-ok",
                    "cwd": ".",
                }
            ),
        )

        from embedagent.workspace_recipes import list_workspace_recipes

        payload = list_workspace_recipes(self.workspace)
        recipe_ids = [item["id"] for item in payload["items"]]
        local = [item for item in payload["items"] if item["id"] == "local.build"][0]

        self.assertIn("local.build", recipe_ids)
        self.assertEqual(local["source"], "local_resource")
        self.assertEqual(local["tool_name"], "run_recipe")

    def test_tool_runtime_reload_resources_updates_recipe_paths(self):
        runtime = ToolRuntime(self.workspace)
        before = runtime.workspace_recipes()

        _write_text(
            os.path.join(self.workspace, ".embedagent", "recipes", "verify.json"),
            json.dumps(
                {
                    "id": "local.verify",
                    "tool_name": "run_recipe",
                    "recipe_action": "test",
                    "label": "Local Verify",
                    "command": "cmd /c echo verify-ok",
                }
            ),
        )
        reloaded = runtime.reload_resources(reason="test")
        after = runtime.workspace_recipes()

        self.assertNotIn("local.verify", [item["id"] for item in before["items"]])
        self.assertEqual(reloaded["counts"]["recipes"], 1)
        self.assertIn("local.verify", [item["id"] for item in after["items"]])

    def test_adapter_reload_resources_records_transcript_events_and_extension_paths(self):
        extra_dir = os.path.join(self.workspace, "extra-recipes")
        _write_text(
            os.path.join(extra_dir, "extra.json"),
            json.dumps(
                {
                    "id": "extra.recipe",
                    "tool_name": "run_recipe",
                    "recipe_action": "build",
                    "label": "Extra Recipe",
                    "command": "cmd /c echo extra",
                }
            ),
        )
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=ToolRuntime(self.workspace),
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        adapter.extension_manager.register(ExtraResourceExtension(extra_dir))
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")

        payload = adapter.reload_resources(session_id=session_id, reason="test")
        recipes = adapter.list_workspace_recipes()
        events = adapter.transcript_store.load_events(session_id)

        self.assertEqual(payload["counts"]["recipes"], 1)
        self.assertIn("extra.recipe", [item["id"] for item in recipes["items"]])
        self.assertTrue(any(item["type"] == "resource_discovered" for item in events))
        self.assertTrue(any(item["type"] == "resource_reloaded" for item in events))

    def test_slash_resources_reload_emits_command_result(self):
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=ToolRuntime(self.workspace),
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "local.md"),
            "# Local Skill\n",
        )
        events = []

        adapter.submit_user_message(
            session_id=session_id,
            text="/resources reload",
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: events.append(
                (event_name, payload)
            ),
        )

        command_results = [
            payload for event_name, payload in events if event_name == "command_result"
        ]
        self.assertEqual(len(command_results), 1)
        self.assertEqual(command_results[0]["command_name"], "resources")
        self.assertTrue(command_results[0]["success"])
        self.assertEqual(command_results[0]["data"]["counts"]["skills"], 1)

    def test_adapter_capability_snapshot_combines_tools_resources_commands_and_model(self):
        _write_text(
            os.path.join(self.workspace, ".embedagent", "prompts", "triage.md"),
            "# Triage\n",
        )
        client = FakeClient()
        client.model = "local-test-model"
        client.base_url = "http://localhost:11434/v1"
        client.api_key = "secret-value"
        adapter = InProcessAdapter(
            client=client,
            tools=ToolRuntime(self.workspace),
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
        )
        adapter.reload_resources(reason="test")

        payload = adapter.capability_snapshot()
        by_kind = {}
        for item in payload["descriptors"]:
            by_kind.setdefault(item["kind"], []).append(item)

        self.assertTrue(any(item["name"] == "read_file" for item in by_kind["tool"]))
        self.assertTrue(
            any(item["name"] == ".embedagent/prompts/triage.md" for item in by_kind["resource"])
        )
        self.assertTrue(any(item["name"] == "help" for item in by_kind["command"]))
        self.assertEqual(by_kind["model_profile"][0]["name"], "local-test-model")
        self.assertNotIn("api_key", by_kind["model_profile"][0]["metadata"])
        self.assertIn("tool", payload["counts"])
        self.assertIn("resource", payload["counts"])


if __name__ == "__main__":
    unittest.main()
