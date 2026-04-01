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


class MultiStepClient(object):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                reasoning_content="先读取文件内容。",
                actions=[
                    Action(
                        name="read_file",
                        arguments={"path": "src/pkg/demo.c"},
                        call_id="call-step-1",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(
            content="分析完成，文件结构正常。",
            reasoning_content="读取完成，总结结果。",
            actions=[],
            finish_reason="stop",
        )

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_reasoning_delta is not None and reply.reasoning_content:
            on_reasoning_delta(reply.reasoning_content)
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

    def test_structured_timeline_splits_single_turn_into_multiple_agent_steps(self):
        adapter = InProcessAdapter(
            client=MultiStepClient(),
            tools=self.tools,
            permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        )
        snapshot = adapter.create_session('code')
        session_id = str(snapshot.get('session_id') or '')
        adapter.submit_user_message(
            session_id=session_id,
            text='请分析这个文件',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, current_session_id, payload: None,
        )
        payload = adapter.build_structured_timeline(session_id)
        self.assertEqual(len(payload["turns"]), 1)
        turn = payload["turns"][0]
        self.assertEqual(turn["user_text"], "请分析这个文件")
        self.assertEqual(len(turn["steps"]), 2)
        self.assertEqual(turn["steps"][0]["tool_calls"][0]["call_id"], "call-step-1")
        self.assertEqual(turn["steps"][0]["reasoning"], "先读取文件内容。")
        self.assertEqual(turn["steps"][1]["assistant_text"], "分析完成，文件结构正常。")
        self.assertEqual(turn["steps"][1]["reasoning"], "读取完成，总结结果。")
        step_ids = [step["step_id"] for step in turn["steps"]]
        self.assertEqual(len(step_ids), len(set(step_ids)))

    def test_session_snapshot_includes_runtime_environment_summary(self):
        snapshot = self.adapter.get_session_snapshot(str(self.snapshot.get('session_id') or ''))
        self.assertIn("runtime_source", snapshot)
        self.assertIn("bundled_tools_ready", snapshot)
        self.assertIn("fallback_warnings", snapshot)
        self.assertIn("runtime_environment", snapshot)
        self.assertIsInstance(snapshot["fallback_warnings"], list)

    def test_workspace_recipe_api_detects_cmake(self):
        with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
        payload = self.adapter.list_workspace_recipes()
        recipe_ids = [item["id"] for item in payload["items"]]
        self.assertIn("cmake.build.default", recipe_ids)
        self.assertIn("cmake.test.default", recipe_ids)

    def test_slash_recipes_emits_recipe_summary(self):
        with open(os.path.join(self.workspace, "Makefile"), "w", encoding="utf-8") as handle:
            handle.write("all:\n\t@echo build\n")
        events = []
        self.adapter.submit_user_message(
            session_id=str(self.snapshot.get('session_id') or ''),
            text='/recipes',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append((event_name, payload)),
        )
        command_events = [payload for event_name, payload in events if event_name == "command_result"]
        self.assertEqual(command_events[0].get("command_name"), "recipes")
        self.assertIn("Workspace Recipes", command_events[0].get("message") or "")
        recipe_ids = [item["id"] for item in command_events[0].get("data", {}).get("items", [])]
        self.assertIn("make.build.default", recipe_ids)

    def test_slash_run_executes_recipe_and_emits_tool_events(self):
        os.makedirs(os.path.join(self.workspace, ".embedagent"), exist_ok=True)
        with open(os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"), "w", encoding="utf-8") as handle:
            handle.write(
                '[{"id":"custom.build","tool_name":"compile_project","label":"Custom Build","command":"cmd /c echo build-ok","cwd":"."}]'
            )
        events = []
        self.adapter.submit_user_message(
            session_id=str(self.snapshot.get('session_id') or ''),
            text='/run custom.build',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append((event_name, payload)),
        )
        event_names = [event_name for event_name, _ in events]
        self.assertIn("tool_started", event_names)
        self.assertIn("tool_finished", event_names)
        command_events = [payload for event_name, payload in events if event_name == "command_result"]
        self.assertEqual(command_events[0].get("command_name"), "run")
        self.assertTrue(command_events[0].get("success"))
        self.assertEqual(command_events[0].get("data", {}).get("recipe_id"), "custom.build")

    def test_slash_run_passes_target_and_profile_to_recipe(self):
        with open(os.path.join(self.workspace, "CMakeLists.txt"), "w", encoding="utf-8") as handle:
            handle.write("cmake_minimum_required(VERSION 3.20)\nproject(demo C)\n")
        events = []
        self.adapter.submit_user_message(
            session_id=str(self.snapshot.get('session_id') or ''),
            text='/run cmake.build.default demo-app debug',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append((event_name, payload)),
        )
        tool_finish = [payload for event_name, payload in events if event_name == "tool_finished"][0]
        self.assertEqual(tool_finish.get("data", {}).get("recipe_id"), "cmake.build.default")
        self.assertEqual(tool_finish.get("data", {}).get("target"), "demo-app")
        self.assertEqual(tool_finish.get("data", {}).get("profile"), "debug")

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
        self.assertEqual(tool_start.get("tool_label"), "Read File")
        self.assertEqual(tool_finish.get("permission_category"), "read")
        self.assertEqual(tool_start.get("progress_renderer_key"), "file")
        self.assertEqual(tool_finish.get("result_renderer_key"), "file")

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

    def test_slash_help_emits_command_result(self):
        events = []
        self.adapter.submit_user_message(
            session_id=str(self.snapshot.get('session_id') or ''),
            text='/help',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append((event_name, payload)),
        )
        command_events = [payload for event_name, payload in events if event_name == "command_result"]
        self.assertEqual(len(command_events), 1)
        self.assertEqual(command_events[0].get("command_name"), "help")
        self.assertIn("Slash Commands", command_events[0].get("message") or "")

    def test_slash_plan_persists_plan_snapshot(self):
        session_id = str(self.snapshot.get('session_id') or '')
        self.adapter.submit_user_message(
            session_id=session_id,
            text='/plan ## Summary\n\n- add tests',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: None,
        )
        snapshot = self.adapter.get_session_snapshot(session_id)
        self.assertTrue(snapshot["has_active_plan"])
        self.assertEqual(snapshot["workflow_state"], "plan")
        plan = self.adapter.get_session_plan(session_id)
        self.assertIsNotNone(plan)
        self.assertIn("add tests", plan.content)

    def test_slash_permissions_reflects_session_memory(self):
        session_id = str(self.snapshot.get('session_id') or '')
        self.adapter.remember_permission_category(session_id, "workspace_write")
        context = self.adapter.get_permission_context(session_id)
        self.assertIn("workspace_write", context.remembered_categories)

    def test_tool_catalog_exposes_renderer_metadata(self):
        items = self.adapter.get_tool_catalog()
        self.assertTrue(any(item.get("name") == "read_file" for item in items))
        read_file = [item for item in items if item.get("name") == "read_file"][0]
        self.assertEqual(read_file.get("user_label"), "Read File")
        self.assertEqual(read_file.get("result_renderer_key"), "file")

    def test_slash_review_emits_structured_findings(self):
        session_id = str(self.snapshot.get('session_id') or '')
        self.adapter.timeline_store.append_event(
            session_id,
            "tool_finished",
            {
                "tool_name": "compile_project",
                "success": False,
                "call_id": "call-build-1",
                "error": "命令退出码为 1。",
                "data": {
                    "diagnostics": [
                        {
                            "file": "src/pkg/demo.c",
                            "line": 2,
                            "column": 5,
                            "message": "expected ';' after return statement",
                        }
                    ]
                },
            },
        )
        events = []
        self.adapter.submit_user_message(
            session_id=session_id,
            text='/review',
            stream=False,
            wait=True,
            permission_resolver=lambda ticket: True,
            event_handler=lambda event_name, session_id, payload: events.append((event_name, payload)),
        )
        command_events = [payload for event_name, payload in events if event_name == "command_result"]
        self.assertEqual(command_events[0].get("command_name"), "review")
        review = command_events[0].get("data", {}).get("review", {})
        findings = review.get("findings") or []
        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "high")
        self.assertIn("Build failed", findings[0]["title"])
        sections = review.get("sections") or {}
        self.assertGreaterEqual(len(sections.get("diagnostics") or []), 1)
        git_sections = sections.get("git") or []
        self.assertGreaterEqual(len(git_sections), 1)
        self.assertIn("diff_preview", git_sections[0])


if __name__ == '__main__':
    unittest.main()
