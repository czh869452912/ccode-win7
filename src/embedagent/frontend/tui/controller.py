from __future__ import annotations

from typing import Dict, Optional

from embedagent_protocol import SessionEventEnvelope

import embedagent.frontend.tui.reducer as reducer
from embedagent.frontend.tui.commands import parse_command
from embedagent.frontend.tui.models import ExplorerItem
from embedagent.frontend.tui.views.timeline import format_activity_records


class TerminalController(object):
    def __init__(self, owner) -> None:
        self.owner = owner
        self.current_summary = None  # type: Optional[Dict[str, object]]
        self.latest_assistant_reply = ""

    def start(self) -> None:
        self.refresh_workspace_snapshot()
        self.refresh_sessions()
        self.refresh_tasks()
        if self.owner.resume_reference:
            self.owner.runtime.resume_session(
                self.owner.resume_reference,
                self.owner.initial_mode,
            )
        else:
            self.owner.runtime.create_session(self.owner.initial_mode)
        reducer.append_line(self.owner.state, "[system] 会话已就绪。")
        self.refresh_explorer(self.owner.state.explorer.tab)
        self.refresh_inspector(self.owner.state.inspector.tab)
        if self.owner.initial_message:
            self.submit_message(self.owner.initial_message)

    def accept_input(self, buffer) -> bool:
        text = buffer.text.strip()
        buffer.text = ""
        if not text:
            return False
        self.handle_input(text)
        return False

    def handle_input(self, text: str) -> None:
        pending = self.owner.state.session.pending_interaction
        if pending is not None:
            if pending.get("kind") == "permission":
                self.handle_permission_reply(text)
            elif pending.get("kind") == "user_input":
                self.handle_user_input_reply(text)
            else:
                reducer.append_line(self.owner.state, "[interaction] unknown pending interaction")
                self.owner.refresh_views()
            return
        if text.startswith("/"):
            self.handle_command(text)
            return
        self.submit_message(text)

    def handle_permission_reply(self, text: str) -> None:
        ticket = self.owner.state.session.pending_interaction or {}
        interaction_id = str(ticket.get("interaction_id") or "")
        normalized = text.strip().lower()
        if normalized in ("y", "yes"):
            self.owner.runtime.respond_to_interaction(
                self.owner.state.session.current_session_id,
                interaction_id,
                {"decision": "accept"},
            )
            reducer.append_line(
                self.owner.state, "[permission] 已批准 %s" % (ticket.get("tool_name") or "")
            )

            self.refresh_inspector(self.owner.state.inspector.tab)
            self.owner.refresh_views()
            return
        if normalized in ("n", "no"):
            self.owner.runtime.respond_to_interaction(
                self.owner.state.session.current_session_id,
                interaction_id,
                {"decision": "decline"},
            )
            reducer.append_line(
                self.owner.state, "[permission] 已拒绝 %s" % (ticket.get("tool_name") or "")
            )

            self.refresh_inspector(self.owner.state.inspector.tab)
            self.owner.refresh_views()
            return
        reducer.append_line(self.owner.state, "[permission] 请输入 y 或 n。")
        self.owner.refresh_views()

    def handle_user_input_reply(self, text: str) -> None:
        ticket = self.owner.state.session.pending_interaction or {}
        interaction_id = str(ticket.get("interaction_id") or "")
        raw = text.strip()
        if not raw:
            reducer.append_line(self.owner.state, "[question] 请输入选项序号或自由文本。")
            self.owner.refresh_views()
            return
        answer = raw
        if raw.isdigit():
            questions = ticket.get("questions") or []
            question = questions[0] if questions and isinstance(questions[0], dict) else {}
            options = question.get("options") or []
            for item in options:
                if not isinstance(item, dict):
                    continue
                if int(item.get("index") or 0) != int(raw):
                    continue
                answer = str(item.get("label") or item.get("value") or item.get("text") or "")
                break
            if answer == raw:
                reducer.append_line(self.owner.state, "[question] 无效选项，请重新输入。")
                self.owner.refresh_views()
                return
        self.owner.runtime.respond_to_interaction(
            self.owner.state.session.current_session_id,
            interaction_id,
            {"answers": {"answer": answer}},
        )
        reducer.append_line(
            self.owner.state,
            "[question] 已回答 %s" % (answer[:96] + ("..." if len(answer) > 96 else "")),
        )

        self.refresh_inspector(self.owner.state.inspector.tab)
        self.owner.refresh_views()

    def handle_command(self, text: str) -> None:
        parsed = parse_command(text)
        try:
            command = self.owner.runtime.resolve_command(parsed.name)
            if str(command.dispatch.get("kind") or "") == "session.command":
                reducer.append_line(self.owner.state, "user> %s" % text)
            self.owner.runtime.execute_command(
                command.id,
                parsed.args,
                default_mode=self.owner.initial_mode,
            )
            self._after_shell_command(command.dispatch)
        except (RuntimeError, ValueError, TypeError) as exc:
            reducer.set_last_error(self.owner.state, str(exc))
            reducer.append_line(self.owner.state, "[error] %s" % exc)
        self.owner.refresh_views()

    def _after_shell_command(self, dispatch: Dict[str, object]) -> None:
        kind = str(dispatch.get("kind") or "")
        if kind in (
            "session.create",
            "session.select",
            "session.rename",
            "session.archive",
            "session.fork",
        ):
            self.refresh_sessions()
        if kind in ("session.create", "session.select", "session.fork"):
            self.refresh_explorer("workspace")
        if kind in (
            "session.create",
            "session.select",
            "session.fork",
            "session.mode",
            "session.cancel",
        ):
            self.refresh_inspector("status")

    def submit_message(self, text: str) -> None:
        session_id = self.owner.state.session.current_session_id
        if not session_id:
            reducer.append_line(self.owner.state, "[error] 当前没有可用会话。")
            self.owner.refresh_views()
            return
        reducer.append_line(self.owner.state, "user> %s" % text)
        reducer.update_snapshot(self.owner.state, status="running", last_error=None)
        reducer.set_last_error(self.owner.state, "")
        try:
            self.owner.runtime.submit_user_message(session_id, text)
        except (RuntimeError, ValueError, TypeError) as exc:
            reducer.set_last_error(self.owner.state, str(exc))
            reducer.update_snapshot(self.owner.state, status="error", last_error=str(exc))
            reducer.append_line(self.owner.state, "[error] %s" % exc)
        self.owner.refresh_views()

    def create_new_session(self, mode: Optional[str] = None) -> None:
        self.owner.runtime.create_session(mode or self.owner.initial_mode)
        reducer.append_line(self.owner.state, "[system] 会话已就绪。")
        self.refresh_sessions()
        self.refresh_explorer("workspace")
        self.refresh_inspector("status")
        self.owner.refresh_views()

    def resume_latest_session(self) -> None:
        self.resume_session("latest")

    def resume_session(self, reference: str) -> None:
        self.owner.runtime.resume_session(reference, self.owner.initial_mode)
        self.refresh_sessions()
        self.refresh_explorer("workspace")
        self.refresh_inspector("status")
        self.owner.refresh_views()

    def show_sessions_explorer(self) -> None:
        self.refresh_explorer("sessions")
        self.owner.refresh_views()

    def show_snapshot(self) -> None:
        self.refresh_inspector("snapshot")
        self.owner.refresh_views()

    def show_help(self) -> None:
        self.refresh_inspector("help")
        self.owner.refresh_views()

    def show_plan(self) -> None:
        self.refresh_tasks()
        self.refresh_inspector("plan")
        self.owner.refresh_views()

    def close_aux_view(self) -> None:
        self.refresh_inspector("status")
        reducer.set_main_view(self.owner.state, "timeline")
        self.owner.refresh_views()

    def move_selection(self, step: int) -> None:
        reducer.move_explorer_selection(self.owner.state, step)
        self.owner.refresh_views()

    def activate_selection(self) -> None:
        item = reducer.current_explorer_item(self.owner.state)
        if item is None:
            return
        if self.owner.state.explorer.tab == "sessions":
            self.resume_session(item.path)
            return
        if self.owner.state.explorer.tab == "workspace":
            if item.kind == "dir":
                self.refresh_explorer("workspace", item.path)
            else:
                self.open_preview(item.path)
            self.owner.refresh_views()
            return
        if self.owner.state.explorer.tab == "tasks":
            self.show_plan()

    def open_selected_preview(self) -> None:
        item = reducer.current_explorer_item(self.owner.state)
        if item is None:
            return
        if item.kind == "file":
            self.open_preview(item.path)
        elif item.kind == "dir":
            self.refresh_explorer("workspace", item.path)
        self.owner.refresh_views()

    def edit_selected_item(self) -> None:
        item = reducer.current_explorer_item(self.owner.state)
        if item is None or item.kind != "file":
            return
        self.open_editor(item.path)
        self.owner.refresh_views()

    def open_preview(self, path: str) -> None:
        try:
            payload = self.owner.runtime.read_workspace_file(path)
        except (OSError, ValueError, TypeError) as exc:
            reducer.append_line(self.owner.state, "[error] %s" % exc)
            return
        text = str(payload.get("content") or "")
        reducer.set_preview(self.owner.state, str(payload.get("path") or path), text)

    def open_editor(self, path: str) -> None:
        try:
            buffer = self.owner.editor_service.open_buffer(path)
        except (OSError, ValueError, TypeError) as exc:
            reducer.append_line(self.owner.state, "[error] %s" % exc)
            return
        reducer.set_editor_buffer(self.owner.state, buffer, diff_preview="", warning="")

    def save_editor(self) -> None:
        buffer = self.owner.state.editor.buffer
        if not buffer.path:
            reducer.append_line(self.owner.state, "[editor] 当前没有打开的文件。")
            return
        if not buffer.dirty:
            reducer.append_line(self.owner.state, "[editor] 没有待保存的修改。")
            return
        result = self.owner.editor_service.save_buffer(buffer)
        reducer.set_editor_buffer(
            self.owner.state,
            buffer,
            diff_preview=str(result.get("diff_preview") or ""),
            warning=str(result.get("warning") or ""),
        )
        self.refresh_workspace_snapshot()
        self.refresh_inspector("diff")
        reducer.append_line(self.owner.state, "[editor] 已保存 %s" % buffer.path)

    def toggle_follow_output(self) -> None:
        reducer.set_follow_output(self.owner.state, not self.owner.state.timeline.follow_output)
        self.owner.refresh_views()

    def open_command_palette(self) -> None:
        reducer.show_command_palette(self.owner.state)
        self.owner.refresh_views()

    def close_command_palette(self) -> None:
        reducer.hide_command_palette(self.owner.state)
        self.owner.refresh_views()

    def execute_workbench_command(self, command_id: str) -> None:
        command = self.owner.state.workbench.command_by_id(command_id)
        if not command.id:
            return
        try:
            self.owner.runtime.execute_command(command.id, [], default_mode=self.owner.initial_mode)
            self._after_shell_command(command.dispatch)
        except (RuntimeError, ValueError, TypeError) as exc:
            reducer.set_last_error(self.owner.state, str(exc))
            reducer.append_line(self.owner.state, "[error] %s" % exc)
        self.owner.refresh_views()

    def on_editor_text_changed(self, _buffer) -> None:
        if self.owner.state.main_view != "editor":
            return
        reducer.update_editor_content(self.owner.state, self.owner.layout.editor.text)
        self.owner.refresh_views()

    def on_runtime_action(self, action: Dict[str, object]) -> None:
        action_type = str(action.get("type") or "") if isinstance(action, dict) else ""
        if action_type == "session_activated":
            self._install_session_bootstrap(action.get("bootstrap"))
            return
        if action_type == "shell_surface":
            self._activate_shell_surface(action.get("surface"))
            return
        if action_type == "shell_command":
            dispatch = action.get("dispatch")
            if isinstance(dispatch, dict) and dispatch.get("kind") == "workspace.open":
                self.refresh_explorer("workspace")
            self.owner.refresh_views()
            return
        if action_type != "session_event":
            return
        envelope = SessionEventEnvelope.from_dict(action.get("event") or {})
        self.owner.frontend.on_session_event(envelope)
        if envelope.event_kind == "session.finished":
            self.refresh_workspace_snapshot()
            self.refresh_sessions()
            self.refresh_tasks()
            self.refresh_session_projection()
        self.refresh_inspector(self.owner.state.inspector.tab)
        self.owner.refresh_views()

    def _activate_shell_surface(self, value) -> None:
        surface = dict(value or {}) if isinstance(value, dict) else {}
        surface_id = str(surface.get("id") or "")
        renderer_key = str(surface.get("renderer_key") or "")
        if renderer_key == "command_palette":
            reducer.show_command_palette(self.owner.state)
        elif renderer_key == "composer":
            self.owner.application.layout.focus(self.owner.composer)
        elif renderer_key == "interaction":
            self.refresh_inspector("status")
        elif renderer_key == "file_reference":
            self.refresh_explorer("workspace")
            reducer.set_workbench_surface(self.owner.state, surface_id)
        elif renderer_key == "workflow_summary":
            self.show_plan()
        elif renderer_key == "inline_diff":
            self.refresh_inspector("diff")
        else:
            reducer.set_workbench_surface(self.owner.state, surface_id)
            self.refresh_inspector(surface_id)
        self.owner.refresh_views()

    def _install_session_bootstrap(self, value) -> None:
        payload = dict(value or {}) if isinstance(value, dict) else {}
        snapshot = dict(payload.get("snapshot") or {})
        history = dict(payload.get("history") or {})
        reducer.reset_session_buffers(self.owner.state)
        reducer.set_snapshot(self.owner.state, snapshot)
        pending = None
        if bool(snapshot.get("pending_interaction_valid")) and isinstance(
            snapshot.get("pending_interaction"), dict
        ):
            pending = dict(snapshot.get("pending_interaction") or {})
        reducer.set_pending_interaction(self.owner.state, pending)
        activities = history.get("activities") or []
        self.owner.state.timeline.lines = format_activity_records(activities)
        self.owner.state.timeline.stream_text = ""
        reducer.trim_timeline(self.owner.state)
        self.latest_assistant_reply = str(
            history.get("latest_assistant_reply") or self.latest_assistant_reply or ""
        )
        self.owner.refresh_views()

    def refresh_workspace_snapshot(self) -> None:
        snapshot = self.owner.runtime.get_workspace_snapshot()
        session_id = self.owner.state.session.current_session_id
        snapshot["tasks"] = self.owner.runtime.list_tasks(session_id=session_id).get("tasks") or []
        reducer.set_workspace_snapshot(self.owner.state, snapshot)

    def refresh_sessions(self) -> None:
        items = self.owner.runtime.list_sessions(self.owner.state.session_limit)
        self.owner.state.session.session_items = items
        if self.owner.state.explorer.tab == "sessions":
            explorer_items = []
            for item in items:
                session_id = str(item.get("session_id") or "")
                label = "%s [%s]" % (session_id[:12], item.get("current_mode") or "-")
                detail = "updated=%s goal=%s" % (
                    item.get("updated_at") or "-",
                    item.get("user_goal") or item.get("summary_text") or "-",
                )
                explorer_items.append(
                    ExplorerItem(kind="session", path=session_id, label=label, detail=detail)
                )
            reducer.set_explorer_items(
                self.owner.state, "sessions", explorer_items, root="sessions"
            )

    def refresh_tasks(self) -> None:
        session_id = self.owner.state.session.current_session_id
        payload = self.owner.runtime.list_tasks(session_id=session_id)
        if self.owner.state.explorer.tab == "tasks":
            explorer_items = []
            for item in payload.get("tasks") or []:
                if not isinstance(item, dict):
                    continue
                prefix = "[x]" if item.get("done") else "[ ]"
                explorer_items.append(
                    ExplorerItem(
                        kind="task",
                        path=str(item.get("id") or ""),
                        label="%s %s" % (prefix, item.get("content") or ""),
                        detail="id=%s" % (item.get("id") or "-"),
                    )
                )
            reducer.set_explorer_items(
                self.owner.state,
                "tasks",
                explorer_items,
                root=payload.get("path") or ".embedagent/memory/sessions/tasks.json",
            )
        self.owner.state.workspace_snapshot["tasks"] = payload.get("tasks") or []

    def refresh_explorer(self, tab: str, root: str = ".") -> None:
        tab_name = (tab or "workspace").lower()
        if tab_name == "sessions":
            self.refresh_sessions()
            return
        if tab_name == "tasks":
            self.refresh_tasks()
            return
        payload = self.owner.runtime.list_workspace_tree(path=root, max_depth=3, limit=200)
        items = []
        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                continue
            indent = "  " * int(item.get("depth") or 0)
            icon = "[D]" if item.get("kind") == "dir" else "[F]"
            label = "%s%s %s" % (indent, icon, item.get("name") or item.get("path") or "")
            items.append(
                ExplorerItem(
                    kind=str(item.get("kind") or "file"),
                    path=str(item.get("path") or ""),
                    label=label,
                )
            )
        reducer.set_explorer_items(
            self.owner.state, "workspace", items, root=str(payload.get("root") or root)
        )

    def refresh_inspector(self, tab: str) -> None:
        reducer.set_inspector_tab(self.owner.state, (tab or "status").lower())
        self.current_summary = self.owner.runtime.load_session_summary(
            str(self.owner.state.session.current_snapshot.get("summary_ref") or "")
        )

    def refresh_session_projection(self) -> None:
        session_id = self.owner.state.session.current_session_id
        if session_id:
            self.owner.runtime.activate_session(session_id, reason="refresh")
