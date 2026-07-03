import json
import os
import shutil
import sys
import unittest
from itertools import count

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_core.session import AssistantReply
from embedagent.tools import ToolRuntime
from embedagent_core.extensions import ResourcesDiscoverResult
from embedagent_core.permissions import PermissionPolicy
from embedagent_core.query_engine import QueryEngine
from embedagent_host.inprocess_adapter import InProcessAdapter

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


class CapturingClient(object):
    def __init__(self):
        self.messages = []

    def generate(self, messages, tools=None):
        del tools
        self.messages.append(messages)
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

    def extension_capabilities(self):
        from embedagent_core.extensions import ExtensionCapability

        return [ExtensionCapability("resources_discover", self.resources_discover)]

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

    def test_discovers_pi_style_skill_frontmatter(self):
        from embedagent.local_resources import discover_local_resources
        from embedagent.skills import format_skills_for_prompt

        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "review", "SKILL.md"),
            "---\n"
            "name: code-review\n"
            "description: Review local C changes for correctness and risk.\n"
            "disable-model-invocation: false\n"
            "---\n"
            "# Code Review\n\n"
            "Use compiler evidence and cite files.\n",
        )
        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "private", "SKILL.md"),
            "---\n"
            "name: private-audit\n"
            "description: Internal checklist that must be invoked explicitly.\n"
            "disable-model-invocation: true\n"
            "---\n"
            "# Private Audit\n",
        )

        payload = discover_local_resources(self.workspace)
        by_name = dict((item["name"], item) for item in payload["skills"])
        prompt_text = format_skills_for_prompt(payload["skills"])

        self.assertEqual(payload["counts"]["skills"], 2)
        self.assertEqual(
            by_name["code-review"]["description"],
            "Review local C changes for correctness and risk.",
        )
        self.assertEqual(by_name["code-review"]["path"], ".embedagent/skills/review/SKILL.md")
        self.assertEqual(by_name["code-review"]["base_dir"], ".embedagent/skills/review")
        self.assertFalse(by_name["code-review"]["disable_model_invocation"])
        self.assertTrue(by_name["code-review"]["prompt_visible"])
        self.assertTrue(by_name["private-audit"]["disable_model_invocation"])
        self.assertFalse(by_name["private-audit"]["prompt_visible"])
        self.assertIn("<available_skills>", prompt_text)
        self.assertIn("<name>code-review</name>", prompt_text)
        self.assertIn(
            "<description>Review local C changes for correctness and risk.</description>",
            prompt_text,
        )
        self.assertIn("<location>.embedagent/skills/review/SKILL.md</location>", prompt_text)
        self.assertNotIn("private-audit", prompt_text)

    def test_expand_skill_invocation_includes_body_and_arguments(self):
        from embedagent.local_resources import discover_local_resources
        from embedagent.skills import expand_skill_invocation

        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "review", "SKILL.md"),
            "---\n"
            "name: code-review\n"
            "description: Review local C changes.\n"
            "---\n"
            "# Code Review\n\n"
            "Use compiler evidence and cite files.\n",
        )

        resources = discover_local_resources(self.workspace)
        expanded, error = expand_skill_invocation(
            "/skill:code-review focus on ownership", resources, self.workspace
        )

        self.assertEqual(error, "")
        self.assertIn(
            '<skill name="code-review" location=".embedagent/skills/review/SKILL.md">',
            expanded,
        )
        self.assertIn("References are relative to .embedagent/skills/review.", expanded)
        self.assertIn("# Code Review", expanded)
        self.assertIn("Use compiler evidence and cite files.", expanded)
        self.assertIn("focus on ownership", expanded)
        self.assertNotIn("description: Review local C changes.", expanded)

    def test_expand_prompt_invocation_includes_body_and_arguments(self):
        from embedagent.local_resources import discover_local_resources
        from embedagent.prompts import expand_prompt_invocation

        _write_text(
            os.path.join(self.workspace, ".embedagent", "prompts", "triage.md"),
            "# Triage Prompt\n\nCollect logs and summarize the failure.\n",
        )

        resources = discover_local_resources(self.workspace)
        expanded, error = expand_prompt_invocation(
            "/prompt:triage focus on startup", resources, self.workspace
        )

        self.assertEqual(error, "")
        self.assertIn(
            '<prompt name="triage" location=".embedagent/prompts/triage.md">',
            expanded,
        )
        self.assertIn("# Triage Prompt", expanded)
        self.assertIn("Collect logs and summarize the failure.", expanded)
        self.assertIn("focus on startup", expanded)

    def test_slash_skill_command_continues_as_user_turn(self):
        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "review", "SKILL.md"),
            "---\n"
            "name: code-review\n"
            "description: Review local C changes.\n"
            "---\n"
            "# Code Review\n\n"
            "Use compiler evidence and cite files.\n",
        )
        client = CapturingClient()
        adapter = InProcessAdapter(
            client=client,
            tools=ToolRuntime(self.workspace),
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        events = []

        adapter.submit_user_message(
            session_id=session_id,
            text="/skill:code-review focus on ownership",
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: events.append(
                (event_name, payload)
            ),
        )

        self.assertTrue(client.messages)
        user_messages = [
            item
            for item in client.messages[0]
            if item.get("role") == "user" and "<skill name=" in str(item.get("content") or "")
        ]
        command_results = [
            payload for event_name, payload in events if event_name == "command_result"
        ]
        self.assertEqual(command_results, [])
        self.assertEqual(len(user_messages), 1)
        self.assertIn("code-review", user_messages[0]["content"])
        self.assertIn("focus on ownership", user_messages[0]["content"])

    def test_slash_prompt_command_continues_as_user_turn(self):
        _write_text(
            os.path.join(self.workspace, ".embedagent", "prompts", "triage.md"),
            "# Triage Prompt\n\nCollect logs and summarize the failure.\n",
        )
        client = CapturingClient()
        adapter = InProcessAdapter(
            client=client,
            tools=ToolRuntime(self.workspace),
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        events = []

        adapter.submit_user_message(
            session_id=session_id,
            text="/prompt:triage focus on startup",
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: events.append(
                (event_name, payload)
            ),
        )

        self.assertTrue(client.messages)
        user_messages = [
            item
            for item in client.messages[0]
            if item.get("role") == "user" and "<prompt name=" in str(item.get("content") or "")
        ]
        command_results = [
            payload for event_name, payload in events if event_name == "command_result"
        ]
        self.assertEqual(command_results, [])
        self.assertEqual(len(user_messages), 1)
        self.assertIn("triage", user_messages[0]["content"])
        self.assertIn("focus on startup", user_messages[0]["content"])

    def test_prompt_resources_are_not_inlined_into_system_prompt(self):
        _write_text(
            os.path.join(self.workspace, ".embedagent", "prompts", "triage.md"),
            "# Triage Prompt\n\nCollect logs and summarize the failure.\n",
        )
        runtime = ToolRuntime(self.workspace)
        runtime.reload_resources(reason="test")
        engine = QueryEngine(FakeClient(), runtime)
        session = engine.submit_user_turn(
            "inspect the change", stream=False, initial_mode="build"
        ).session
        system_text = "\n\n".join(
            message.content for message in session.messages if message.role == "system"
        )

        self.assertNotIn("# Triage Prompt", system_text)
        self.assertNotIn("Collect logs and summarize the failure.", system_text)

    def test_query_engine_system_prompt_does_not_inline_visible_skills(self):
        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "review", "SKILL.md"),
            "---\n"
            "name: code-review\n"
            "description: Review local C changes.\n"
            "---\n"
            "# Code Review\n",
        )
        runtime = ToolRuntime(self.workspace)
        runtime.reload_resources(reason="test")
        engine = QueryEngine(FakeClient(), runtime)
        session = engine.submit_user_turn(
            "inspect the change", stream=False, initial_mode="build"
        ).session
        system_text = "\n\n".join(
            message.content for message in session.messages if message.role == "system"
        )

        self.assertNotIn("<available_skills>", system_text)
        self.assertNotIn("<name>code-review</name>", system_text)

    def test_skill_discovery_honors_ignore_files(self):
        from embedagent.local_resources import discover_local_resources

        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", ".gitignore"),
            "ignored/\n*.tmp.md\n",
        )
        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "visible", "SKILL.md"),
            "---\nname: visible-skill\ndescription: Visible skill.\n---\n# Visible\n",
        )
        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "ignored", "SKILL.md"),
            "---\nname: ignored-skill\ndescription: Ignored skill.\n---\n# Ignored\n",
        )
        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "draft.tmp.md"),
            "---\nname: draft-skill\ndescription: Draft skill.\n---\n# Draft\n",
        )

        payload = discover_local_resources(self.workspace)
        names = [item["name"] for item in payload["skills"]]

        self.assertEqual(names, ["visible-skill"])

    def test_skill_discovery_ignore_negation_can_reinclude_file(self):
        from embedagent.local_resources import discover_local_resources

        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", ".ignore"),
            "*.md\n!keep.md\n",
        )
        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "keep.md"),
            "---\nname: keep-skill\ndescription: Keep skill.\n---\n# Keep\n",
        )
        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "drop.md"),
            "---\nname: drop-skill\ndescription: Drop skill.\n---\n# Drop\n",
        )

        payload = discover_local_resources(self.workspace)

        self.assertEqual([item["name"] for item in payload["skills"]], ["keep-skill"])

    def test_skill_index_projects_prompt_commands_and_lookup(self):
        from embedagent.local_resources import discover_local_resources
        from embedagent.skill_index import build_skill_index

        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "review", "SKILL.md"),
            "---\nname: code-review\ndescription: Review local C changes.\n---\n# Review\n",
        )
        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "private", "SKILL.md"),
            (
                "---\n"
                "name: private-audit\n"
                "description: Hidden.\n"
                "disable-model-invocation: true\n"
                "---\n"
                "# Private\n"
            ),
        )

        index = build_skill_index(discover_local_resources(self.workspace))

        self.assertEqual([item.name for item in index.visible_records()], ["code-review"])
        self.assertEqual(index.record_by_name("code-review").base_dir, ".embedagent/skills/review")
        self.assertFalse(index.record_by_name("private-audit").prompt_visible)
        self.assertIn("<name>code-review</name>", index.prompt_text())
        self.assertEqual([spec.name for spec in index.command_specs()], ["skill:code-review"])

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
        projected = adapter.get_session_snapshot(session_id)
        runtime_config = projected.get("runtime_config") or {}
        resource_revision = runtime_config.get("resource_revision") or {}

        self.assertEqual(payload["counts"]["recipes"], 1)
        self.assertIn("extra.recipe", [item["id"] for item in recipes["items"]])
        self.assertTrue(any(item["type"] == "resource_discovered" for item in events))
        self.assertTrue(any(item["type"] == "resource_reloaded" for item in events))
        self.assertTrue(any(item["type"] == "runtime_configured" for item in events))
        self.assertEqual(resource_revision["revision"], 2)
        self.assertEqual(resource_revision["reason"], "test")
        self.assertEqual(resource_revision["counts"]["recipes"], 1)

    def test_session_runtime_config_records_registered_and_active_tool_names(self):
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=ToolRuntime(self.workspace),
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        runtime_config = snapshot.get("runtime_config") or {}
        registered_tool_names = runtime_config.get("registered_tool_names") or []
        active_tool_names = runtime_config.get("active_tool_names") or []

        self.assertIn("read_file", registered_tool_names)
        self.assertIn("run_recipe", registered_tool_names)
        self.assertIn("read_file", active_tool_names)
        self.assertIn("run_recipe", active_tool_names)

    def test_resumed_session_projects_runtime_config_from_transcript(self):
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
        adapter.reload_resources(session_id=session_id, reason="test")

        reloaded = InProcessAdapter(
            client=FakeClient(),
            tools=ToolRuntime(self.workspace),
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        resumed = reloaded.resume_session(session_id, "build")
        runtime_config = resumed.get("runtime_config") or {}
        resource_revision = runtime_config.get("resource_revision") or {}

        self.assertEqual(resource_revision["revision"], 2)
        self.assertEqual(resource_revision["reason"], "test")
        self.assertEqual(resource_revision["counts"]["skills"], 1)

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
        self.assertIn("capabilities", command_results[0]["data"]["read_model_invalidations"])

    def test_session_start_skill_prompt_is_single_prompt_surface(self):
        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "review", "SKILL.md"),
            "---\n"
            "name: code-review\n"
            "description: Review local C changes.\n"
            "---\n"
            "# Code Review\n",
        )
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=ToolRuntime(self.workspace),
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )

        snapshot = adapter.create_session("build")
        state = adapter._require_session(str(snapshot.get("session_id") or ""))
        skill_prompts = [
            message
            for message in state.session.messages
            if message.role == "system" and message.kind == "local_skills_prompt"
        ]
        system_prompt_text = "\n\n".join(
            message.content
            for message in state.session.messages
            if message.role == "system" and message.kind != "local_skills_prompt"
        )

        self.assertEqual(len(skill_prompts), 1)
        self.assertIn("<name>code-review</name>", skill_prompts[0].content)
        self.assertNotIn("<name>code-review</name>", system_prompt_text)
        self.assertEqual(
            "\n\n".join(message.content for message in state.session.messages).count(
                "<name>code-review</name>"
            ),
            1,
        )

    def test_reload_resources_refreshes_current_session_skill_prompt(self):
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=ToolRuntime(self.workspace),
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        state = adapter._require_session(session_id)
        initial_system = "\n\n".join(
            message.content for message in state.session.messages if message.role == "system"
        )
        self.assertNotIn("code-review", initial_system)

        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "review", "SKILL.md"),
            "---\n"
            "name: code-review\n"
            "description: Review local C changes.\n"
            "---\n"
            "# Code Review\n",
        )
        adapter.reload_resources(session_id=session_id, reason="test")

        skill_prompts = [
            message
            for message in state.session.messages
            if message.role == "system" and message.kind == "local_skills_prompt"
        ]
        events = adapter.transcript_store.load_events(session_id)
        message_events = [item for item in events if item["type"] == "message"]

        self.assertEqual(len(skill_prompts), 1)
        self.assertIn("<name>code-review</name>", skill_prompts[0].content)
        self.assertEqual(skill_prompts[0].metadata["reason"], "test")
        self.assertTrue(
            any(
                str((item.get("payload") or {}).get("kind") or "") == "local_skills_prompt"
                for item in message_events
            )
        )

        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "review", "SKILL.md"),
            "---\n"
            "name: code-review-v2\n"
            "description: Review local C changes with ownership notes.\n"
            "---\n"
            "# Code Review\n",
        )
        adapter.reload_resources(session_id=session_id, reason="test-second")
        skill_prompts = [
            message
            for message in state.session.messages
            if message.role == "system" and message.kind == "local_skills_prompt"
        ]

        self.assertEqual(len(skill_prompts), 1)
        self.assertIn("<name>code-review-v2</name>", skill_prompts[0].content)
        self.assertNotIn("<name>code-review</name>", skill_prompts[0].content)
        self.assertEqual(skill_prompts[0].metadata["reason"], "test-second")

    def test_help_and_capability_snapshot_include_visible_skill_commands(self):
        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "review", "SKILL.md"),
            "---\n"
            "name: code-review\n"
            "description: Review local C changes.\n"
            "---\n"
            "# Code Review\n",
        )
        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "private", "SKILL.md"),
            "---\n"
            "name: private-audit\n"
            "description: Hidden checklist.\n"
            "disable-model-invocation: true\n"
            "---\n"
            "# Private Audit\n",
        )
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=ToolRuntime(self.workspace),
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        adapter.reload_resources(reason="test")
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        events = []

        adapter.submit_user_message(
            session_id=session_id,
            text="/help",
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: events.append(
                (event_name, payload)
            ),
        )
        command_results = [
            payload for event_name, payload in events if event_name == "command_result"
        ]
        capabilities = adapter.capability_snapshot()
        command_names = [
            item["name"] for item in capabilities["descriptors"] if item["kind"] == "command"
        ]

        self.assertEqual(len(command_results), 1)
        self.assertIn("/skill:code-review [args]", command_results[0]["message"])
        self.assertIn("Review local C changes.", command_results[0]["message"])
        self.assertNotIn("private-audit", command_results[0]["message"])
        self.assertIn("skill:code-review", command_names)
        self.assertNotIn("skill:private-audit", command_names)

    def test_help_and_capability_snapshot_include_visible_resource_commands(self):
        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "review", "SKILL.md"),
            "---\n"
            "name: code-review\n"
            "description: Review local C changes.\n"
            "---\n"
            "# Code Review\n",
        )
        _write_text(
            os.path.join(self.workspace, ".embedagent", "prompts", "triage.md"),
            "# Triage Prompt\n\nCollect logs and summarize the failure.\n",
        )
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=ToolRuntime(self.workspace),
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        adapter.reload_resources(reason="test")
        snapshot = adapter.create_session("build")
        session_id = str(snapshot.get("session_id") or "")
        events = []

        adapter.submit_user_message(
            session_id=session_id,
            text="/help",
            stream=False,
            wait=True,
            event_handler=lambda event_name, current_session_id, payload: events.append(
                (event_name, payload)
            ),
        )
        command_results = [
            payload for event_name, payload in events if event_name == "command_result"
        ]
        capabilities = adapter.capability_snapshot()
        command_names = [
            item["name"] for item in capabilities["descriptors"] if item["kind"] == "command"
        ]

        self.assertEqual(len(command_results), 1)
        self.assertIn("/skill:code-review [args]", command_results[0]["message"])
        self.assertIn("/prompt:triage [args]", command_results[0]["message"])
        self.assertIn("skill:code-review", command_names)
        self.assertIn("prompt:triage", command_names)

    def test_session_bootstrap_includes_dynamic_resource_commands(self):
        _write_text(
            os.path.join(self.workspace, ".embedagent", "skills", "review", "SKILL.md"),
            "---\n"
            "name: code-review\n"
            "description: Review local C changes.\n"
            "---\n"
            "# Review\n",
        )
        _write_text(
            os.path.join(self.workspace, ".embedagent", "prompts", "triage.md"),
            "# Triage\n",
        )
        adapter = InProcessAdapter(
            client=FakeClient(),
            tools=ToolRuntime(self.workspace),
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session(mode="explore")
        session_id = snapshot["session_id"]
        adapter.reload_resources(session_id=session_id, reason="test")

        bootstrap = adapter.get_session_bootstrap(session_id)
        commands = bootstrap["capabilities"]["commands"]
        usages = [item["usage"] for item in commands]

        self.assertIn("/resources [reload]", usages)
        self.assertIn("/skill:code-review [args]", usages)
        self.assertIn("/prompt:triage [args]", usages)

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
        self.assertIn("workflow_package", payload["counts"])

        package_items = [
            item for item in payload["descriptors"] if item["kind"] == "workflow_package"
        ]

        self.assertEqual(len(package_items), 1)
        self.assertEqual(package_items[0]["name"], "embedagent.c_workflow")
        self.assertEqual(package_items[0]["metadata"]["label"], "C/C++ Workflow")
        self.assertIn(
            "build_lite",
            [item["name"] for item in package_items[0]["metadata"]["packs"]],
        )


if __name__ == "__main__":
    unittest.main()
