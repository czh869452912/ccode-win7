from __future__ import annotations

import json
import os
import sys
import threading
from typing import Any, Dict

from embedagent.cli import main as cli_main
from embedagent.inprocess_adapter import InProcessAdapter
from embedagent.permissions import PermissionPolicy
from embedagent.session import Action, AssistantReply
from embedagent.tools import ToolRuntime
from embedagent.tui import EmbedAgentTUI


ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))


def _print(title: str, value: str) -> None:
    sys.stdout.write("[%s] %s\n" % (title, value))


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class FakeClient(object):
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="先读取 README。",
                actions=[Action(name="read_file", arguments={"path": "README.md"}, call_id="call-read")],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="adapter-ok", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class FakeSummaryStore(object):
    def load_summary(self, reference):
        return {
            "summary_ref": reference,
            "user_goal": "验证 Phase 6",
            "working_set": ["src/embedagent/tui.py"],
            "modified_files": ["src/embedagent/cli.py"],
            "recent_actions": [{"name": "read_file"}, {"name": "run_command"}],
            "recent_artifacts": [{"path": ".embedagent/memory/artifacts/test.json"}],
            "last_success": {"tool_name": "read_file", "path": "README.md"},
            "last_blocker": {"tool_name": "run_command", "exit_code": 1, "error": "sample error"},
            "context_stats": {"recent_turns": 2, "summarized_turns": 3, "approx_tokens_after": 900},
        }


class FakeTUIAdapter(object):
    def __init__(self) -> None:
        self.summary_store = FakeSummaryStore()

    def create_session(self, mode, event_handler=None):
        return {
            "session_id": "sess-live",
            "current_mode": mode,
            "status": "idle",
            "updated_at": "2026-03-28T13:00:00Z",
            "summary_ref": ".embedagent/memory/sessions/sess-live/summary.json",
        }

    def resume_session(self, reference, mode="", event_handler=None):
        return {
            "session_id": "sess-live",
            "current_mode": mode or "code",
            "status": "idle",
            "updated_at": "2026-03-28T13:00:00Z",
            "summary_ref": ".embedagent/memory/sessions/sess-live/summary.json",
        }

    def list_sessions(self, limit=10):
        return [
            {
                "session_id": "sess-live",
                "current_mode": "code",
                "updated_at": "2026-03-28T13:00:00Z",
                "user_goal": "验证 TUI 可启动",
            },
            {
                "session_id": "sess-prev",
                "current_mode": "debug",
                "updated_at": "2026-03-28T12:00:00Z",
                "user_goal": "上一次会话",
            },
        ][:limit]

    def submit_user_message(self, session_id, text, stream=True, wait=False, permission_resolver=None, event_handler=None):
        def worker():
            if event_handler is None:
                return
            event_handler("turn_started", session_id, {"text": text, "stream": stream})
            event_handler("assistant_delta", session_id, {"text": "正在验证 TUI "})
            event_handler("tool_started", session_id, {"tool_name": "read_file", "arguments": {"path": "README.md"}})
            event_handler("tool_finished", session_id, {"tool_name": "read_file", "success": True, "error": None, "data": {"path": "README.md"}})
            event_handler(
                "permission_required",
                session_id,
                {
                    "permission": {
                        "permission_id": "perm-1",
                        "tool_name": "run_command",
                        "category": "command",
                        "reason": "需要执行命令",
                        "details": {"command": "python -m py_compile src/embedagent/tui.py"},
                    }
                },
            )
            event_handler(
                "context_compacted",
                session_id,
                {
                    "recent_turns": 2,
                    "summarized_turns": 4,
                    "approx_tokens_after": 1024,
                    "project_memory_included": True,
                },
            )
            event_handler(
                "session_finished",
                session_id,
                {
                    "final_text": "验证完成",
                    "session_snapshot": {
                        "session_id": session_id,
                        "current_mode": "code",
                        "status": "idle",
                        "updated_at": "2026-03-28T13:00:02Z",
                        "summary_ref": ".embedagent/memory/sessions/sess-live/summary.json",
                        "has_pending_permission": False,
                        "pending_permission": None,
                        "last_error": None,
                    },
                },
            )

        threading.Thread(target=worker, daemon=True).start()
        return {"session_id": session_id, "status": "running"}

    def approve_permission(self, session_id, permission_id):
        return {
            "session_id": session_id,
            "status": "running",
            "summary_ref": ".embedagent/memory/sessions/sess-live/summary.json",
            "has_pending_permission": False,
            "pending_permission": None,
        }

    def reject_permission(self, session_id, permission_id):
        return {
            "session_id": session_id,
            "status": "running",
            "summary_ref": ".embedagent/memory/sessions/sess-live/summary.json",
            "has_pending_permission": False,
            "pending_permission": None,
        }

    def set_session_mode(self, session_id, mode):
        return {
            "session_id": session_id,
            "current_mode": mode,
            "status": "idle",
            "summary_ref": ".embedagent/memory/sessions/sess-live/summary.json",
        }


def validate_inprocess_adapter() -> Dict[str, Any]:
    tools = ToolRuntime(ROOT)
    adapter = InProcessAdapter(
        client=FakeClient(),
        tools=tools,
        max_turns=4,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=ROOT),
    )
    events = []

    def on_event(event_name, session_id, payload):
        events.append(event_name)

    snapshot = adapter.create_session("code", event_handler=on_event)
    result = adapter.submit_user_message(
        session_id=str(snapshot.get("session_id") or ""),
        text="请读取 README",
        stream=False,
        wait=True,
        permission_resolver=lambda ticket: True,
        event_handler=on_event,
    )
    switched = adapter.set_session_mode(str(snapshot.get("session_id") or ""), "debug")
    _ensure(result.get("status") == "idle", "adapter 同步提交后状态不为 idle。")
    _ensure(switched.get("current_mode") == "debug", "adapter set_session_mode 未生效。")
    _ensure("tool_started" in events and "tool_finished" in events, "adapter 事件流不完整。")
    return {
        "session_id": str(snapshot.get("session_id") or ""),
        "events": len(events),
        "mode": str(switched.get("current_mode") or ""),
    }


def validate_cli_tui_guard() -> Dict[str, Any]:
    exit_code = cli_main(["--workspace", ROOT, "--model", "fake-model", "--tui"])
    _ensure(exit_code == 1, "非控制台宿主下 --tui 应返回 1。")
    return {"exit_code": exit_code, "guard": "ok"}


def validate_headless_tui() -> Dict[str, Any]:
    old_value = os.environ.get("EMBEDAGENT_TUI_HEADLESS")
    os.environ["EMBEDAGENT_TUI_HEADLESS"] = "1"
    try:
        app = EmbedAgentTUI(
            adapter=FakeTUIAdapter(),
            workspace=ROOT,
            initial_mode="code",
            initial_message="请做一次启动验证",
        )
        threading.Timer(1.0, app.application.exit).start()
        result = app.run()
        _ensure(result == 0, "headless TUI 未正常退出。")
        _ensure(any("context" in line for line in app.transcript_lines), "headless TUI 未记录 context 事件。")
        _ensure("Session" in app.side_panel.text and "Context" in app.side_panel.text, "headless TUI 侧栏未显示摘要块。")
        return {
            "result": result,
            "transcript_lines": len(app.transcript_lines),
            "status": str(app.current_snapshot.get("status") or ""),
        }
    finally:
        if old_value is None:
            del os.environ["EMBEDAGENT_TUI_HEADLESS"]
        else:
            os.environ["EMBEDAGENT_TUI_HEADLESS"] = old_value


def main() -> int:
    adapter = validate_inprocess_adapter()
    _print("adapter", json.dumps(adapter, ensure_ascii=False, sort_keys=True))
    guard = validate_cli_tui_guard()
    _print("cli_guard", json.dumps(guard, ensure_ascii=False, sort_keys=True))
    headless = validate_headless_tui()
    _print("headless_tui", json.dumps(headless, ensure_ascii=False, sort_keys=True))
    _print("result", "PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
