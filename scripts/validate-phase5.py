from __future__ import annotations

import json
import os
import shutil
import sys
from typing import Any, Dict, Optional

from embedagent.context import ContextManager
from embedagent.loop import AgentLoop
from embedagent.permissions import PermissionPolicy
from embedagent.project_memory import ProjectMemoryStore
from embedagent.session import Action, AssistantReply
from embedagent.session_store import SessionSummaryStore
from embedagent.tools import ToolRuntime


ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
WORK_ROOT = os.path.join(ROOT, ".embedagent", "validation")


def _print(title: str, value: str) -> None:
    sys.stdout.write("[%s] %s\n" % (title, value))


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _py_command(code: str) -> str:
    return '"%s" -c "%s"' % (sys.executable, code.replace('"', '\\"'))


def _reset_workspace(path: str) -> None:
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(os.path.join(path, "src"))
    with open(os.path.join(path, "AGENTS.md"), "w", encoding="utf-8") as handle:
        handle.write(
            "Windows 7 compatibility is mandatory.\n"
            "Offline deployment is mandatory.\n"
            "Primary development environment manager: `uv`\n"
            "conda is the approved fallback\n"
            "zero external dependencies\n"
        )
    with open(os.path.join(path, "pyproject.toml"), "w", encoding="utf-8") as handle:
        handle.write('requires-python = ">=3.8,<3.9"\n')
    with open(os.path.join(path, "README.md"), "w", encoding="utf-8") as handle:
        handle.write("EmbedAgent validation workspace\n")
    with open(os.path.join(path, "src", "sample.py"), "w", encoding="utf-8") as handle:
        handle.write("def sample():\n    return 'old'\n")


class RoundClient(object):
    def __init__(self, action: Optional[Action], first_text: str, final_text: str = "done") -> None:
        self.action = action
        self.first_text = first_text
        self.final_text = final_text
        self.calls = []
        self._index = 0

    def stream(self, messages, tools=None, on_text_delta=None):
        return self.generate(messages, tools=tools)

    def generate(self, messages, tools=None):
        self.calls.append(messages)
        self._index += 1
        if self._index == 1 and self.action is not None:
            return AssistantReply(content=self.first_text, actions=[self.action])
        return AssistantReply(content=self.final_text, actions=[])


class InspectClient(object):
    def __init__(self) -> None:
        self.calls = []

    def stream(self, messages, tools=None, on_text_delta=None):
        return self.generate(messages, tools=tools)

    def generate(self, messages, tools=None):
        self.calls.append(messages)
        return AssistantReply(content="resume-ok", actions=[])


def validate_long_task() -> Dict[str, Any]:
    workspace = os.path.join(WORK_ROOT, "long_task")
    _reset_workspace(workspace)
    tools = ToolRuntime(workspace)
    summary_store = SessionSummaryStore(workspace)
    project_store = ProjectMemoryStore(workspace)
    permission_policy = PermissionPolicy(auto_approve_all=True, workspace=workspace)

    steps = [
        lambda i: (Action("read_file", {"path": "README.md"}, "read_%s" % i), "读取 README"),
        lambda i: (Action("search_text", {"query": "validation", "path": "."}, "search_%s" % i), "搜索 validation"),
        lambda i: (Action("run_command", {"command": _py_command("print('X'*2500)"), "cwd": "."}, "cmd_%s" % i), "执行大输出命令"),
        lambda i: (Action("switch_mode", {"target": "verify"}, "mode_verify_%s" % i), "切到 verify"),
        lambda i: (Action("compile_project", {"command": _py_command("import sys; print('compile fail'); sys.exit(1)"), "cwd": "."}, "compile_%s" % i), "故意编译失败"),
        lambda i: (Action("switch_mode", {"target": "code"}, "mode_code_%s" % i), "切回 code"),
        lambda i: (Action("edit_file", {"path": "src/sample.py", "old_text": "return 'old'", "new_text": "return 'new_%s'" % i}, "edit_%s" % i), "修改文件"),
        lambda i: (Action("run_tests", {"command": _py_command("import sys; print('test fail'); sys.exit(2)"), "cwd": "."}, "tests_%s" % i), "故意测试失败"),
    ]

    session = None
    current_mode = "code"
    for index in range(24):
        action, text = steps[index % len(steps)](index)
        client = RoundClient(action, text)
        loop = AgentLoop(
            client=client,
            tools=tools,
            max_turns=4,
            permission_policy=permission_policy,
            summary_store=summary_store,
            project_memory_store=project_store,
            maintenance_interval=2,
        )
        loop_result = loop.run(
            user_text="turn-%02d" % index,
            stream=False,
            initial_mode=current_mode,
            session=session,
        )
        session = loop_result.session
        if action.name == "switch_mode":
            current_mode = str(action.arguments.get("target") or current_mode)

    _ensure(session is not None, "长任务会话未创建。")
    _ensure(len(session.turns) >= 24, "长任务 turn 数不足。")
    context = ContextManager(project_memory=project_store).build_messages(session, current_mode)
    _ensure(context.stats.summarized_turns > 0, "上下文未发生历史摘要化。")
    _ensure(context.stats.project_memory_included, "项目记忆未注入上下文。")
    latest = summary_store.load_summary("latest")
    _ensure(int(latest.get("turn_count") or 0) >= 24, "摘要文件未记录长任务 turn 数。")
    resumed = summary_store.create_resumed_session(latest, latest.get("current_mode"))
    resume_loop = AgentLoop(
        client=RoundClient(Action("search_text", {"query": "validation", "path": "."}, "resume_search"), "恢复后继续执行"),
        tools=tools,
        max_turns=4,
        permission_policy=permission_policy,
        summary_store=summary_store,
        project_memory_store=project_store,
    )
    resumed_result = resume_loop.run(
        user_text="恢复后继续",
        stream=False,
        initial_mode=str(latest.get("current_mode") or current_mode),
        session=resumed,
    )
    resumed_session = resumed_result.session
    _ensure(len(resumed_session.turns) == 1, "恢复后的会话应以摘要续跑，而不是全量回放。")
    inspect_client = InspectClient()
    resume_loop = AgentLoop(
        client=inspect_client,
        tools=tools,
        max_turns=2,
        permission_policy=permission_policy,
        summary_store=summary_store,
        project_memory_store=project_store,
    )
    resume_loop.run(
        user_text="继续长任务",
        stream=False,
        initial_mode=str(latest.get("current_mode") or current_mode),
        session=resumed,
    )
    system_messages = [item.get("content", "") for item in inspect_client.calls[0] if item.get("role") == "system"]
    _ensure(any("恢复摘要" in item for item in system_messages), "恢复消息未注入系统提示。")
    _ensure(any("项目级记忆" in item for item in system_messages), "恢复后项目记忆未注入。")
    artifact_index = tools.projection_db.list_tool_results(limit=20)
    return {
        "turns": len(session.turns),
        "summarized_turns": context.stats.summarized_turns,
        "artifacts": len(artifact_index),
        "mode": current_mode,
    }


def validate_permissions() -> Dict[str, Any]:
    workspace = os.path.join(WORK_ROOT, "permissions")
    _reset_workspace(workspace)
    os.makedirs(os.path.join(workspace, ".embedagent"))
    rules = {
        "schema_version": 1,
        "rules": [
            {
                "decision": "deny",
                "category": "write",
                "tool_names": ["edit_file"],
                "path_globs": ["README.md"],
                "reason": "README 不允许被自动修改。",
            },
            {
                "decision": "allow",
                "category": "write",
                "tool_names": ["edit_file"],
                "path_globs": ["src/*.py", "src/**/*.py"],
                "reason": "允许修改源码目录。",
            },
            {
                "decision": "deny",
                "category": "command",
                "command_patterns": [r"(^|\s)(del|rm)\b"],
                "reason": "禁止危险删除命令。",
            },
            {
                "decision": "ask",
                "category": "command",
                "tool_names": ["run_command"],
                "command_patterns": [r"python"],
                "reason": "执行 Python 命令需要人工确认。",
            },
        ],
    }
    with open(os.path.join(workspace, ".embedagent", "permission-rules.json"), "w", encoding="utf-8") as handle:
        json.dump(rules, handle, ensure_ascii=False, indent=2, sort_keys=True)

    policy = PermissionPolicy(workspace=workspace, rules_path='.embedagent/permission-rules.json')
    allow_decision = policy.evaluate(Action('edit_file', {'path': 'src/sample.py', 'old_text': "return 'old'", 'new_text': "return 'ok'"}, 'allow'))
    deny_decision = policy.evaluate(Action('edit_file', {'path': 'README.md', 'old_text': 'EmbedAgent', 'new_text': 'changed'}, 'deny'))
    ask_decision = policy.evaluate(Action('run_command', {'command': _py_command("print(1)")}, 'ask'))
    cmd_deny_decision = policy.evaluate(Action('run_command', {'command': 'del temp.txt'}, 'cmd_deny'))
    _ensure(allow_decision.outcome == 'allow', '源码目录写入规则未放行。')
    _ensure(deny_decision.outcome == 'deny', 'README deny 规则未生效。')
    _ensure(ask_decision.outcome == 'ask', 'Python 命令 ask 规则未生效。')
    _ensure(cmd_deny_decision.outcome == 'deny', '危险命令 deny 规则未生效。')

    tools = ToolRuntime(workspace)
    summary_store = SessionSummaryStore(workspace)
    project_store = ProjectMemoryStore(workspace)
    loop = AgentLoop(
        client=RoundClient(Action('edit_file', {'path': 'src/sample.py', 'old_text': "return 'old'", 'new_text': "return 'patched'"}, 'loop_allow'), '修改源码'),
        tools=tools,
        max_turns=3,
        permission_policy=policy,
        summary_store=summary_store,
        project_memory_store=project_store,
    )
    allow_result = loop.run('允许的修改', stream=False, initial_mode='code')
    session_allow = allow_result.session
    _ensure(session_allow.turns[0].observations[0].success, '允许规则下 edit_file 未执行成功。')
    updated = open(os.path.join(workspace, 'src', 'sample.py'), 'r', encoding='utf-8').read()
    _ensure('patched' in updated, '允许规则下文件未被修改。')

    loop = AgentLoop(
        client=RoundClient(Action('edit_file', {'path': 'README.md', 'old_text': 'EmbedAgent', 'new_text': 'Nope'}, 'loop_deny'), '尝试修改 README'),
        tools=tools,
        max_turns=3,
        permission_policy=policy,
        summary_store=summary_store,
        project_memory_store=project_store,
    )
    deny_result = loop.run('拒绝的修改', stream=False, initial_mode='code')
    session_deny = deny_result.session
    deny_obs = session_deny.turns[0].observations[0]
    _ensure(not deny_obs.success and deny_obs.data.get('permission_decision') == 'deny', 'deny 规则未在 loop 中返回拒绝 Observation。')

    loop = AgentLoop(
        client=RoundClient(Action('run_command', {'command': _py_command("print(2)")}, 'loop_ask'), '尝试执行 Python 命令'),
        tools=tools,
        max_turns=3,
        permission_policy=policy,
        summary_store=summary_store,
        project_memory_store=project_store,
    )
    ask_result = loop.run('需要确认的命令', stream=False, initial_mode='debug', permission_handler=lambda request: False)
    session_ask = ask_result.session
    ask_obs = session_ask.turns[0].observations[0]
    _ensure(not ask_obs.success and ask_obs.data.get('permission_decision') == 'deny', 'ask 规则经用户拒绝后未返回 deny Observation。')
    return {
        "rules": len(policy.rules),
        "allow": allow_decision.outcome,
        "deny": deny_decision.outcome,
        "ask": ask_decision.outcome,
    }


def main() -> int:
    if not os.path.isdir(WORK_ROOT):
        os.makedirs(WORK_ROOT)
    long_task = validate_long_task()
    _print('long_task', json.dumps(long_task, ensure_ascii=False, sort_keys=True))
    permissions = validate_permissions()
    _print('permissions', json.dumps(permissions, ensure_ascii=False, sort_keys=True))
    _print('result', 'PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
