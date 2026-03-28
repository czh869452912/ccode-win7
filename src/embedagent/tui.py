from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

from embedagent.inprocess_adapter import InProcessAdapter
from embedagent.llm import OpenAICompatibleClient
from embedagent.modes import DEFAULT_MODE
from embedagent.permissions import PermissionPolicy
from embedagent.tools import ToolRuntime


class TUIUnavailableError(RuntimeError):
    pass


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _load_tui_dependencies():
    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit, VSplit, Layout
        from prompt_toolkit.layout.containers import Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.input.defaults import create_pipe_input
        from prompt_toolkit.output import DummyOutput
        from prompt_toolkit.output.win32 import NoConsoleScreenBufferError
        from prompt_toolkit.widgets import TextArea
        from rich.console import Console
    except ImportError as exc:
        raise TUIUnavailableError(
            "TUI 依赖未安装。请先安装 `prompt_toolkit` 与 `rich` 后再运行 `--tui`。"
        ) from exc
    return {
        "Application": Application,
        "KeyBindings": KeyBindings,
        "HSplit": HSplit,
        "VSplit": VSplit,
        "Layout": Layout,
        "Window": Window,
        "FormattedTextControl": FormattedTextControl,
        "TextArea": TextArea,
        "Console": Console,
        "create_pipe_input": create_pipe_input,
        "DummyOutput": DummyOutput,
        "NoConsoleScreenBufferError": NoConsoleScreenBufferError,
    }


class EmbedAgentTUI(object):
    def __init__(
        self,
        adapter: InProcessAdapter,
        workspace: str,
        initial_mode: str = DEFAULT_MODE,
        resume_reference: str = "",
        initial_message: str = "",
        session_limit: int = 10,
        transcript_limit: int = 240,
    ) -> None:
        deps = _load_tui_dependencies()
        self.Application = deps["Application"]
        self.KeyBindings = deps["KeyBindings"]
        self.HSplit = deps["HSplit"]
        self.VSplit = deps["VSplit"]
        self.Layout = deps["Layout"]
        self.Window = deps["Window"]
        self.FormattedTextControl = deps["FormattedTextControl"]
        self.TextArea = deps["TextArea"]
        self.Console = deps["Console"]
        self.create_pipe_input = deps["create_pipe_input"]
        self.DummyOutput = deps["DummyOutput"]
        self.NoConsoleScreenBufferError = deps["NoConsoleScreenBufferError"]

        self.adapter = adapter
        self.workspace = workspace
        self.initial_mode = initial_mode
        self.resume_reference = resume_reference
        self.initial_message = (initial_message or "").strip()
        self.session_limit = max(1, int(session_limit))
        self.transcript_limit = max(40, int(transcript_limit))

        self.current_session_id = ""
        self.current_snapshot = {}  # type: Dict[str, object]
        self.pending_permission = None  # type: Optional[Dict[str, object]]
        self.transcript_lines = []  # type: List[str]
        self.session_items = []  # type: List[Dict[str, object]]
        self.session_selection = 0
        self.side_view = "summary"
        self.last_context_event = {}  # type: Dict[str, object]
        self.last_error = ""
        self._stream_open = False
        self._stream_line = ""
        self._lock = threading.RLock()
        self._headless = os.environ.get("EMBEDAGENT_TUI_HEADLESS", "").strip() == "1"
        self._pipe_input_cm = None
        self._pipe_input = None

        self.header = self.TextArea(read_only=True, focusable=False, height=2)
        self.transcript = self.TextArea(read_only=True, scrollbar=True, focusable=False, wrap_lines=True)
        self.side_panel = self.TextArea(read_only=True, focusable=False, width=44, wrap_lines=True)
        self.composer = self.TextArea(multiline=False, prompt="user> ", height=1)
        self.composer.accept_handler = self._accept_input

        self.application = self._create_application()

    def run(self) -> int:
        try:
            if self.resume_reference:
                snapshot = self.adapter.resume_session(self.resume_reference, self.initial_mode, event_handler=self._on_event)
                self._append_line("[system] 已恢复会话 %s" % snapshot.get("session_id", ""))
            else:
                snapshot = self.adapter.create_session(self.initial_mode, event_handler=self._on_event)
                self._append_line("[system] 已创建会话 %s" % snapshot.get("session_id", ""))
            self._append_line("[system] 输入消息回车发送，/help 查看命令。")
            self._set_snapshot(snapshot)
            self._refresh_sessions()
            self._refresh_views()
            if self.initial_message:
                self._submit_message(self.initial_message)
            self.application.run()
            return 0
        finally:
            self._close_application_resources()

    def _create_application(self):
        kwargs = {
            "layout": self._build_layout(),
            "key_bindings": self._build_key_bindings(),
            "full_screen": not self._headless,
        }
        if self._headless:
            self._pipe_input_cm = self.create_pipe_input()
            self._pipe_input = self._pipe_input_cm.__enter__()
            kwargs["input"] = self._pipe_input
            kwargs["output"] = self.DummyOutput()
        try:
            return self.Application(**kwargs)
        except self.NoConsoleScreenBufferError as exc:
            self._close_application_resources()
            raise TUIUnavailableError(
                "当前终端不支持全屏 TUI。请在 cmd.exe、Windows Terminal 或支持控制台缓冲区的终端中运行。"
            ) from exc

    def _close_application_resources(self) -> None:
        if self._pipe_input_cm is None:
            return
        try:
            self._pipe_input_cm.__exit__(None, None, None)
        finally:
            self._pipe_input_cm = None
            self._pipe_input = None

    def _build_layout(self):
        header_window = self.Window(
            content=self.FormattedTextControl(text=lambda: self.header.text),
            height=2,
        )
        body = self.VSplit(
            [
                self.transcript,
                self.Window(width=1, char="|"),
                self.side_panel,
            ]
        )
        return self.Layout(
            self.HSplit(
                [
                    header_window,
                    self.Window(height=1, char="-"),
                    body,
                    self.Window(height=1, char="-"),
                    self.composer,
                ]
            )
        )

    def _build_key_bindings(self):
        bindings = self.KeyBindings()

        @bindings.add("c-c")
        @bindings.add("c-q")
        def _(event):
            event.app.exit()

        @bindings.add("f1")
        def _(event):
            self._show_help()

        @bindings.add("f2")
        def _(event):
            self._new_session()

        @bindings.add("f3")
        def _(event):
            self._resume_latest()

        @bindings.add("f4")
        def _(event):
            self._toggle_sessions()

        @bindings.add("f5")
        def _(event):
            self._resume_selected_session()

        @bindings.add("f6")
        def _(event):
            self._show_snapshot()

        @bindings.add("escape")
        def _(event):
            self._close_side_view()

        @bindings.add("up")
        def _(event):
            if self.side_view == "sessions":
                self._move_session_selection(-1)

        @bindings.add("down")
        def _(event):
            if self.side_view == "sessions":
                self._move_session_selection(1)

        return bindings

    def _accept_input(self, buffer) -> bool:
        text = buffer.text.strip()
        buffer.text = ""
        if not text:
            return False
        self._handle_input(text)
        return False

    def _handle_input(self, text: str) -> None:
        if self.pending_permission is not None:
            self._handle_permission_reply(text)
            return
        if text.startswith("/"):
            self._handle_command(text)
            return
        self._submit_message(text)

    def _submit_message(self, text: str) -> None:
        if not self.current_session_id:
            self._append_line("[error] 当前没有可用会话。")
            self._refresh_views()
            return
        self._append_line("user> %s" % text)
        self._update_snapshot(status="running", last_error=None)
        self.last_error = ""
        try:
            self.adapter.submit_user_message(
                self.current_session_id,
                text,
                stream=True,
                wait=False,
                permission_resolver=None,
                event_handler=self._on_event,
            )
        except Exception as exc:
            self.last_error = str(exc)
            self._update_snapshot(status="error", last_error=self.last_error)
            self._append_line("[error] %s" % self.last_error)
        self._refresh_views()

    def _handle_permission_reply(self, text: str) -> None:
        normalized = text.strip().lower()
        ticket = self.pending_permission or {}
        permission_id = str(ticket.get("permission_id") or "")
        if normalized in ("y", "yes"):
            snapshot = self.adapter.approve_permission(self.current_session_id, permission_id)
            self._append_line("[permission] 已批准 %s" % (ticket.get("tool_name") or ""))
            self.pending_permission = None
            self._set_snapshot(snapshot)
            self._update_snapshot(has_pending_permission=False, pending_permission=None, status="running")
            self._refresh_views()
            return
        if normalized in ("n", "no"):
            snapshot = self.adapter.reject_permission(self.current_session_id, permission_id)
            self._append_line("[permission] 已拒绝 %s" % (ticket.get("tool_name") or ""))
            self.pending_permission = None
            self._set_snapshot(snapshot)
            self._update_snapshot(has_pending_permission=False, pending_permission=None, status="running")
            self._refresh_views()
            return
        self._append_line("[permission] 请输入 y 或 n。")
        self._refresh_views()

    def _handle_command(self, text: str) -> None:
        parts = text.split()
        command = parts[0].lower()
        if command == "/quit":
            self.application.exit()
            return
        if command == "/help":
            self._show_help()
            return
        if command == "/new":
            mode = parts[1] if len(parts) > 1 else self.initial_mode
            self._new_session(mode)
            return
        if command == "/resume":
            if len(parts) > 1 and parts[1].lower() == "selected":
                self._resume_selected_session()
                return
            reference = parts[1] if len(parts) > 1 else "latest"
            self._resume_session(reference)
            return
        if command == "/sessions":
            self._show_sessions()
            return
        if command == "/snapshot":
            self._show_snapshot()
            return
        if command == "/close":
            self._close_side_view()
            return
        if command == "/mode":
            if len(parts) < 2:
                self._append_line("[system] 用法：/mode <name>")
            else:
                snapshot = self.adapter.set_session_mode(self.current_session_id, parts[1])
                self._set_snapshot(snapshot)
                self._append_line("[system] 已切换到 %s 模式" % parts[1])
            self._refresh_views()
            return
        self._append_line("[system] 未知命令：%s" % text)
        self._refresh_views()

    def _new_session(self, mode: Optional[str] = None) -> None:
        snapshot = self.adapter.create_session(mode or self.initial_mode, event_handler=self._on_event)
        self.transcript_lines = []
        self._stream_open = False
        self._stream_line = ""
        self.pending_permission = None
        self.last_context_event = {}
        self.last_error = ""
        self.side_view = "summary"
        self._append_line("[system] 已创建会话 %s" % snapshot.get("session_id", ""))
        self._append_line("[system] 输入消息回车发送，/help 查看命令。")
        self._set_snapshot(snapshot)
        self._refresh_sessions()
        self._refresh_views()

    def _resume_latest(self) -> None:
        self._resume_session("latest")

    def _resume_session(self, reference: str) -> None:
        snapshot = self.adapter.resume_session(reference, self.initial_mode, event_handler=self._on_event)
        self.transcript_lines = []
        self._stream_open = False
        self._stream_line = ""
        self.pending_permission = None
        self.last_context_event = {}
        self.last_error = ""
        self.side_view = "summary"
        self._append_line("[system] 已恢复会话 %s" % snapshot.get("session_id", ""))
        self._set_snapshot(snapshot)
        self._refresh_sessions()
        self._refresh_views()

    def _toggle_sessions(self) -> None:
        if self.side_view == "sessions":
            self._close_side_view()
            return
        self._show_sessions()

    def _show_sessions(self) -> None:
        self._refresh_sessions()
        self.side_view = "sessions"
        self._refresh_views()

    def _resume_selected_session(self) -> None:
        self._refresh_sessions()
        if not self.session_items:
            self._append_line("[sessions] 当前没有可恢复的会话。")
            self._refresh_views()
            return
        index = max(0, min(self.session_selection, len(self.session_items) - 1))
        item = self.session_items[index]
        reference = str(item.get("session_id") or item.get("summary_ref") or "latest")
        self._resume_session(reference)

    def _move_session_selection(self, step: int) -> None:
        if not self.session_items:
            self.session_selection = 0
            self._refresh_views()
            return
        limit = len(self.session_items) - 1
        self.session_selection = max(0, min(limit, self.session_selection + step))
        self._refresh_views()

    def _show_snapshot(self) -> None:
        self.side_view = "snapshot"
        self._refresh_views()

    def _show_help(self) -> None:
        self.side_view = "help"
        self._refresh_views()

    def _close_side_view(self) -> None:
        if self.side_view != "summary":
            self.side_view = "summary"
            self._refresh_views()

    def _refresh_sessions(self) -> None:
        items = self.adapter.list_sessions(limit=self.session_limit)
        self.session_items = items
        if not items:
            self.session_selection = 0
            return
        self.session_selection = max(0, min(self.session_selection, len(items) - 1))

    def _set_snapshot(self, snapshot: Dict[str, object]) -> None:
        with self._lock:
            self.current_snapshot = dict(snapshot)
            self.current_session_id = str(snapshot.get("session_id") or "")

    def _update_snapshot(self, **updates: object) -> None:
        with self._lock:
            merged = dict(self.current_snapshot)
            merged.update(updates)
            self.current_snapshot = merged
            self.current_session_id = str(merged.get("session_id") or self.current_session_id or "")

    def _on_event(self, event_name: str, session_id: str, payload: Dict[str, object]) -> None:
        with self._lock:
            if event_name == "turn_started":
                self._close_stream()
                self._update_snapshot(status="running", last_error=None)
            elif event_name == "assistant_delta":
                self._update_snapshot(status="running")
                self._append_delta(str(payload.get("text") or ""))
            elif event_name == "tool_started":
                self._close_stream()
                self._update_snapshot(status="running")
                self._append_line(
                    "[tool] %s %s"
                    % (payload.get("tool_name") or "", payload.get("arguments") or {})
                )
            elif event_name == "tool_finished":
                self._close_stream()
                self._update_snapshot(status="running")
                self._append_line(self._format_observation_line(payload))
            elif event_name == "permission_required":
                permission = payload.get("permission") or {}
                if isinstance(permission, dict):
                    self.pending_permission = permission
                    self._close_stream()
                    self._update_snapshot(
                        status="waiting_permission",
                        has_pending_permission=True,
                        pending_permission=permission,
                    )
                    self._append_line("[permission] %s" % (permission.get("reason") or "需要确认"))
            elif event_name == "session_finished":
                self._close_stream()
                self.pending_permission = None
                snapshot = payload.get("session_snapshot")
                if isinstance(snapshot, dict):
                    self._set_snapshot(snapshot)
                else:
                    self._update_snapshot(status="idle", has_pending_permission=False, pending_permission=None)
                self.last_error = ""
                self._refresh_sessions()
            elif event_name == "session_resumed":
                self.pending_permission = None
                snapshot = payload.get("session_snapshot")
                if isinstance(snapshot, dict):
                    self._set_snapshot(snapshot)
                self.last_error = ""
                self._append_line("[system] 会话已恢复")
                self._refresh_sessions()
            elif event_name == "session_created":
                snapshot = payload.get("session_snapshot")
                if isinstance(snapshot, dict):
                    self._set_snapshot(snapshot)
                self._refresh_sessions()
            elif event_name == "session_error":
                self._close_stream()
                self.last_error = str(payload.get("error") or "")
                self.pending_permission = None
                self._update_snapshot(
                    status="error",
                    last_error=self.last_error,
                    has_pending_permission=False,
                    pending_permission=None,
                )
                self._append_line("[error] %s" % self.last_error)
            elif event_name == "context_compacted":
                self.last_context_event = dict(payload)
                self._append_line(self._format_context_line(payload))
        self._refresh_views()

    def _format_observation_line(self, payload: Dict[str, object]) -> str:
        tool_name = str(payload.get("tool_name") or "")
        success = bool(payload.get("success"))
        data = payload.get("data")
        error = str(payload.get("error") or "")
        parts = ["[observation] %s success=%s" % (tool_name, success)]
        if isinstance(data, dict):
            if data.get("path"):
                parts.append("path=%s" % data.get("path"))
            if data.get("command"):
                parts.append("cmd=%s" % _truncate_text(str(data.get("command") or ""), 80))
            if data.get("exit_code") is not None:
                parts.append("exit=%s" % data.get("exit_code"))
            if data.get("error_count") is not None:
                parts.append("errors=%s" % data.get("error_count"))
            if data.get("warning_count") is not None:
                parts.append("warnings=%s" % data.get("warning_count"))
            if data.get("failed") is not None:
                parts.append("failed=%s" % data.get("failed"))
            if data.get("passed") is not None:
                parts.append("passed=%s" % data.get("passed"))
            for key in sorted(data.keys()):
                if key.endswith("_artifact_ref") and data.get(key):
                    parts.append("%s=%s" % (key[:-13], data.get(key)))
                    break
        if error:
            parts.append("error=%s" % _truncate_text(error, 80))
        return " ".join(parts)

    def _format_context_line(self, payload: Dict[str, object]) -> str:
        parts = ["[context]"]
        if payload.get("recent_turns") is not None:
            parts.append("recent=%s" % payload.get("recent_turns"))
        if payload.get("summarized_turns") is not None:
            parts.append("summarized=%s" % payload.get("summarized_turns"))
        if payload.get("approx_tokens_after") is not None:
            parts.append("tokens=%s" % payload.get("approx_tokens_after"))
        if payload.get("project_memory_included") is not None:
            parts.append("project_memory=%s" % bool(payload.get("project_memory_included")))
        return " ".join(parts)

    def _append_line(self, line: str) -> None:
        self._close_stream()
        self.transcript_lines.append(line)
        if len(self.transcript_lines) > self.transcript_limit:
            self.transcript_lines = self.transcript_lines[-self.transcript_limit :]

    def _append_delta(self, text: str) -> None:
        if not text:
            return
        if not self._stream_open:
            self._stream_open = True
            self._stream_line = "assistant> "
        self._stream_line += text

    def _close_stream(self) -> None:
        if not self._stream_open:
            return
        self.transcript_lines.append(self._stream_line)
        if len(self.transcript_lines) > self.transcript_limit:
            self.transcript_lines = self.transcript_lines[-self.transcript_limit :]
        self._stream_line = ""
        self._stream_open = False

    def _refresh_views(self) -> None:
        self.header.text = self._build_header_text()
        self.transcript.text = self._build_transcript_text()
        self.side_panel.text = self._build_side_panel_text()
        if self.pending_permission is not None:
            self.composer.prompt = "confirm(y/n)> "
        else:
            self.composer.prompt = "user> "
        self.application.invalidate()

    def _build_header_text(self) -> str:
        snapshot = self.current_snapshot
        last_error = self.last_error or str(snapshot.get("last_error") or "")
        second_line = "view=%s  resume=%s" % (
            self.side_view,
            bool(snapshot.get("summary_ref")),
        )
        if self.pending_permission is not None:
            second_line += "  permission=waiting"
        if last_error:
            second_line += "  error=%s" % _truncate_text(last_error, 72)
        return (
            "session=%s  mode=%s  status=%s  workspace=%s\n"
            "%s"
        ) % (
            str(snapshot.get("session_id") or "-")[:12],
            snapshot.get("current_mode") or "-",
            snapshot.get("status") or "idle",
            self.workspace,
            second_line,
        )

    def _build_transcript_text(self) -> str:
        parts = list(self.transcript_lines)
        if self._stream_open:
            parts.append(self._stream_line)
        return "\n".join(parts)

    def _build_side_panel_text(self) -> str:
        if self.side_view == "sessions":
            return self._build_sessions_panel_text()
        if self.side_view == "snapshot":
            return self._build_snapshot_panel_text()
        if self.side_view == "help":
            return self._build_help_panel_text()
        return self._build_summary_panel_text()

    def _build_summary_panel_text(self) -> str:
        snapshot = self.current_snapshot
        summary = self._load_current_summary()
        lines = ["Session"]
        lines.append("- id: %s" % (snapshot.get("session_id") or "-"))
        lines.append("- mode: %s" % (snapshot.get("current_mode") or "-"))
        lines.append("- status: %s" % (snapshot.get("status") or "-"))
        lines.append("- updated: %s" % (snapshot.get("updated_at") or "-"))
        lines.append("")
        lines.append("Context")
        context_stats = {}
        if isinstance(summary, dict):
            maybe_stats = summary.get("context_stats")
            if isinstance(maybe_stats, dict):
                context_stats = dict(maybe_stats)
        if self.last_context_event:
            for key, value in self.last_context_event.items():
                if value is not None:
                    context_stats[key] = value
        lines.append("- recent: %s" % context_stats.get("recent_turns", "-"))
        lines.append("- summarized: %s" % context_stats.get("summarized_turns", "-"))
        lines.append("- tokens: %s" % context_stats.get("approx_tokens_after", "-"))
        if "project_memory_included" in context_stats:
            lines.append("- project_memory: %s" % bool(context_stats.get("project_memory_included")))
        if isinstance(summary, dict):
            lines.append("")
            lines.append("Work")
            lines.append("- goal: %s" % _truncate_text(str(summary.get("user_goal") or "-"), 80))
            lines.append("- working_set: %s" % self._format_join(summary.get("working_set") or [], 4))
            lines.append("- modified: %s" % self._format_join(summary.get("modified_files") or [], 4))
            recent_actions = summary.get("recent_actions") or []
            action_names = []
            for item in recent_actions[:4]:
                if isinstance(item, dict) and item.get("name"):
                    action_names.append(str(item.get("name")))
            lines.append("- actions: %s" % self._format_join(action_names, 4))
            lines.append("")
            lines.append("Status")
            last_success = summary.get("last_success") or {}
            last_blocker = summary.get("last_blocker") or {}
            if isinstance(last_success, dict) and last_success:
                lines.append("- success: %s" % self._format_observation_snapshot(last_success))
            if isinstance(last_blocker, dict) and last_blocker:
                lines.append("- blocker: %s" % self._format_observation_snapshot(last_blocker))
            artifacts = summary.get("recent_artifacts") or []
            if artifacts:
                lines.append("- artifacts: %s" % len(artifacts))
        if self.pending_permission is not None:
            permission = self.pending_permission
            lines.append("")
            lines.append("Permission")
            lines.append("- tool: %s" % (permission.get("tool_name") or "-"))
            lines.append("- category: %s" % (permission.get("category") or "-"))
            lines.append("- reason: %s" % _truncate_text(str(permission.get("reason") or "-"), 96))
            details = permission.get("details") or {}
            if isinstance(details, dict):
                target = details.get("path") or details.get("command") or details.get("cwd")
                if target:
                    lines.append("- target: %s" % _truncate_text(str(target), 96))
        if self.last_error or snapshot.get("last_error"):
            lines.append("")
            lines.append("Error")
            lines.append("- %s" % _truncate_text(self.last_error or str(snapshot.get("last_error") or ""), 96))
        return "\n".join(lines)

    def _build_sessions_panel_text(self) -> str:
        lines = ["Sessions"]
        lines.append("F5 or /resume selected  |  Esc close")
        lines.append("")
        if not self.session_items:
            lines.append("当前没有可恢复的会话。")
            return "\n".join(lines)
        for index, item in enumerate(self.session_items):
            prefix = ">" if index == self.session_selection else " "
            lines.append(
                "%s %d. %s [%s]"
                % (
                    prefix,
                    index + 1,
                    str(item.get("session_id") or "")[:12],
                    item.get("current_mode") or "-",
                )
            )
            lines.append("  updated: %s" % (item.get("updated_at") or "-"))
            goal = str(item.get("user_goal") or item.get("summary_text") or "-")
            lines.append("  goal: %s" % _truncate_text(goal, 84))
            if index >= self.session_limit - 1:
                break
        return "\n".join(lines)

    def _build_snapshot_panel_text(self) -> str:
        lines = ["Snapshot", "Esc close", ""]
        payload = dict(self.current_snapshot)
        if self.pending_permission is not None:
            payload["pending_permission"] = self.pending_permission
        if self.last_context_event:
            payload["last_context_event"] = self.last_context_event
        lines.append(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return "\n".join(lines)

    def _build_help_panel_text(self) -> str:
        lines = ["Help"]
        lines.append("Esc close")
        lines.append("")
        lines.append("Commands")
        lines.append("/help")
        lines.append("/new [mode]")
        lines.append("/resume latest")
        lines.append("/resume selected")
        lines.append("/sessions")
        lines.append("/snapshot")
        lines.append("/mode <name>")
        lines.append("/close")
        lines.append("/quit")
        lines.append("")
        lines.append("Keys")
        lines.append("F1 help")
        lines.append("F2 new")
        lines.append("F3 resume latest")
        lines.append("F4 sessions")
        lines.append("F5 resume selected")
        lines.append("F6 snapshot")
        lines.append("Up/Down move selection")
        lines.append("Ctrl-C / Ctrl-Q exit")
        if self.pending_permission is not None:
            lines.append("")
            lines.append("Permission")
            lines.append("输入 y / n 处理当前确认。")
        return "\n".join(lines)

    def _load_current_summary(self) -> Optional[Dict[str, Any]]:
        summary_ref = str(self.current_snapshot.get("summary_ref") or "")
        if not summary_ref:
            return None
        try:
            return self.adapter.summary_store.load_summary(summary_ref)
        except Exception:
            return None

    def _format_join(self, items: List[Any], limit: int) -> str:
        values = []
        for item in items[:limit]:
            text = str(item or "").strip()
            if text:
                values.append(text)
        if not values:
            return "-"
        return ", ".join(values)

    def _format_observation_snapshot(self, snapshot: Dict[str, object]) -> str:
        parts = [str(snapshot.get("tool_name") or "-")]
        if snapshot.get("path"):
            parts.append("path=%s" % snapshot.get("path"))
        if snapshot.get("exit_code") is not None:
            parts.append("exit=%s" % snapshot.get("exit_code"))
        if snapshot.get("error"):
            parts.append("error=%s" % _truncate_text(str(snapshot.get("error") or ""), 64))
        return " ".join(parts)


def run_tui(
    base_url: str,
    api_key: str,
    model: str,
    workspace: str,
    timeout: float,
    max_turns: int,
    mode: str,
    resume: str,
    approve_all: bool,
    approve_writes: bool,
    approve_commands: bool,
    permission_rules: str,
    initial_message: str = "",
) -> int:
    client = OpenAICompatibleClient(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout=timeout,
    )
    tools = ToolRuntime(workspace)
    permission_policy = PermissionPolicy(
        auto_approve_all=approve_all,
        auto_approve_writes=approve_writes,
        auto_approve_commands=approve_commands,
        workspace=workspace,
        rules_path=permission_rules,
    )
    adapter = InProcessAdapter(
        client=client,
        tools=tools,
        max_turns=max_turns,
        permission_policy=permission_policy,
    )
    app = EmbedAgentTUI(
        adapter=adapter,
        workspace=os.path.realpath(workspace),
        initial_mode=mode or DEFAULT_MODE,
        resume_reference=resume,
        initial_message=initial_message,
    )
    return app.run()


