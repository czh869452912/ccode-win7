from __future__ import annotations

import json
from typing import Dict, Optional

import embedagent.frontend.tui.reducer as reducer
from embedagent.frontend.tui.commands import parse_command
from embedagent.frontend.tui.models import ArtifactRow, ExplorerItem
from embedagent.frontend.tui.views.timeline import (
    format_activity_records,
    format_context_line,
    format_observation_line,
)
from embedagent.frontend.tui.workbench import command_by_id


class TerminalController(object):
    def __init__(self, owner) -> None:
        self.owner = owner
        self.current_summary = None  # type: Optional[Dict[str, object]]
        self.latest_assistant_reply = ""

    def start(self) -> None:
        self.refresh_workspace_snapshot()
        self.refresh_sessions()
        self.refresh_tasks()
        self.refresh_artifacts()
        if self.owner.resume_reference:
            snapshot = self.owner.session_service.resume_session(
                self.owner.resume_reference,
                self.owner.initial_mode,
                event_handler=self.on_event,
            )
            reducer.reset_session_buffers(self.owner.state)
            reducer.set_snapshot(self.owner.state, snapshot)
            self.reload_timeline()
        else:
            snapshot = self.owner.session_service.create_session(
                self.owner.initial_mode,
                event_handler=self.on_event,
            )
            reducer.reset_session_buffers(self.owner.state)
            reducer.set_snapshot(self.owner.state, snapshot)
            self.reload_timeline()
        reducer.append_line(self.owner.state, "[system] 输入消息回车发送，/help 查看命令。")
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
            snapshot = self.owner.session_service.respond_to_interaction(
                self.owner.state.session.current_session_id,
                interaction_id,
                {"decision": "accept"},
            )
            reducer.append_line(
                self.owner.state, "[permission] 已批准 %s" % (ticket.get("tool_name") or "")
            )
            reducer.set_pending_interaction(self.owner.state, None)
            reducer.set_snapshot(self.owner.state, snapshot)
            reducer.update_snapshot(
                self.owner.state,
                pending_interaction=None,
                pending_interaction_valid=False,
                status="running",
            )
            self.refresh_inspector(self.owner.state.inspector.tab)
            self.owner.refresh_views()
            return
        if normalized in ("n", "no"):
            snapshot = self.owner.session_service.respond_to_interaction(
                self.owner.state.session.current_session_id,
                interaction_id,
                {"decision": "decline"},
            )
            reducer.append_line(
                self.owner.state, "[permission] 已拒绝 %s" % (ticket.get("tool_name") or "")
            )
            reducer.set_pending_interaction(self.owner.state, None)
            reducer.set_snapshot(self.owner.state, snapshot)
            reducer.update_snapshot(
                self.owner.state,
                pending_interaction=None,
                pending_interaction_valid=False,
                status="running",
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
        snapshot = self.owner.session_service.respond_to_interaction(
            self.owner.state.session.current_session_id,
            interaction_id,
            {"answers": {"answer": answer}},
        )
        reducer.append_line(
            self.owner.state,
            "[question] 已回答 %s" % (answer[:96] + ("..." if len(answer) > 96 else "")),
        )
        reducer.set_pending_interaction(self.owner.state, None)
        reducer.set_snapshot(self.owner.state, snapshot)
        updates = {
            "pending_interaction": None,
            "pending_interaction_valid": False,
            "status": "running",
        }
        reducer.update_snapshot(self.owner.state, **updates)
        self.refresh_inspector(self.owner.state.inspector.tab)
        self.owner.refresh_views()

    def handle_command(self, text: str) -> None:
        command = parse_command(text)
        name = command.name
        args = command.args
        if name == "quit":
            self.owner.application.exit()
            return
        if name == "help":
            self.show_help()
            return
        if name == "palette":
            self.open_command_palette()
            return
        if name == "new":
            self.create_new_session(args[0] if args else self.owner.initial_mode)
            return
        if name == "resume":
            reference = args[0] if args else "latest"
            if reference == "selected":
                self.activate_selection()
            else:
                self.resume_session(reference)
            return
        if name == "sessions":
            self.show_sessions_explorer()
            return
        if name == "snapshot":
            self.show_snapshot()
            return
        if name == "close":
            self.close_aux_view()
            return
        if name == "mode":
            if not args:
                reducer.append_line(self.owner.state, "[system] 用法：/mode <name>")
            else:
                snapshot = self.owner.session_service.set_mode(
                    self.owner.state.session.current_session_id, args[0]
                )
                reducer.set_snapshot(self.owner.state, snapshot)
                reducer.append_line(self.owner.state, "[system] 已切换到 %s 模式" % args[0])
                self.refresh_inspector(self.owner.state.inspector.tab)
            self.owner.refresh_views()
            return
        if name in ("plan", "review", "diff", "permissions"):
            self.submit_message(text)
            return
        if name == "workspace":
            self.refresh_explorer("workspace", args[0] if args else ".")
            self.owner.refresh_views()
            return
        if name == "tasks":
            self.refresh_explorer("tasks")
            self.show_plan()
            self.owner.refresh_views()
            return
        if name == "artifacts":
            self.show_artifacts()
            self.owner.refresh_views()
            return
        if name == "artifact":
            if not args:
                reducer.append_line(self.owner.state, "[system] 用法：/artifact <ref>")
            else:
                self.open_artifact(args[0])
            self.owner.refresh_views()
            return
        if name == "open":
            if not args:
                reducer.append_line(self.owner.state, "[system] 用法：/open <path>")
            else:
                self.open_preview(args[0])
            self.owner.refresh_views()
            return
        if name == "edit":
            if not args:
                reducer.append_line(self.owner.state, "[system] 用法：/edit <path>")
            else:
                self.open_editor(args[0])
            self.owner.refresh_views()
            return
        if name == "save":
            self.save_editor()
            self.owner.refresh_views()
            return
        if name == "explorer":
            self.refresh_explorer(args[0] if args else "workspace")
            self.owner.refresh_views()
            return
        if name == "inspector":
            self.refresh_inspector(args[0] if args else "status")
            self.owner.refresh_views()
            return
        if name == "follow":
            value = (args[0] if args else "on").lower()
            reducer.set_follow_output(self.owner.state, value != "off")
            self.owner.refresh_views()
            return
        reducer.append_line(self.owner.state, "[system] 未知命令：%s" % text)
        self.owner.refresh_views()

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
            self.owner.session_service.submit(session_id, text, event_handler=self.on_event)
        except (RuntimeError, ValueError, TypeError) as exc:
            reducer.set_last_error(self.owner.state, str(exc))
            reducer.update_snapshot(self.owner.state, status="error", last_error=str(exc))
            reducer.append_line(self.owner.state, "[error] %s" % exc)
        self.owner.refresh_views()

    def create_new_session(self, mode: Optional[str] = None) -> None:
        snapshot = self.owner.session_service.create_session(
            mode or self.owner.initial_mode, event_handler=self.on_event
        )
        reducer.reset_session_buffers(self.owner.state)
        reducer.set_snapshot(self.owner.state, snapshot)
        self.reload_timeline()
        reducer.append_line(self.owner.state, "[system] 输入消息回车发送，/help 查看命令。")
        self.refresh_sessions()
        self.refresh_explorer("workspace")
        self.refresh_inspector("status")
        self.owner.refresh_views()

    def resume_latest_session(self) -> None:
        self.resume_session("latest")

    def resume_session(self, reference: str) -> None:
        snapshot = self.owner.session_service.resume_session(
            reference, self.owner.initial_mode, event_handler=self.on_event
        )
        reducer.reset_session_buffers(self.owner.state)
        reducer.set_snapshot(self.owner.state, snapshot)
        self.reload_timeline()
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

    def show_artifacts(self) -> None:
        self.refresh_artifacts()
        self.refresh_inspector("artifacts")
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
            payload = self.owner.workspace_service.read_file(path)
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

    def open_artifact(self, reference: str) -> None:
        try:
            payload = self.owner.artifact_service.read_item(reference)
        except (OSError, ValueError, TypeError) as exc:
            reducer.append_line(self.owner.state, "[error] %s" % exc)
            return
        reducer.set_selected_artifact(self.owner.state, str(payload.get("path") or reference))
        content = payload.get("content")
        if isinstance(content, str):
            preview = content
        else:
            preview = json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True)
        reducer.set_preview(self.owner.state, str(payload.get("path") or reference), preview)
        self.refresh_inspector("artifacts")

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
        command = command_by_id(command_id)
        if not command.id:
            return
        if command.surface:
            reducer.set_workbench_surface(self.owner.state, command.surface)
            self.refresh_inspector(command.surface)
            self.owner.refresh_views()
            return
        if command.drawer:
            reducer.set_workbench_drawer(self.owner.state, command.drawer)
            self.owner.refresh_views()
            return
        if command.slash:
            self.handle_command(command.slash)

    def on_editor_text_changed(self, _buffer) -> None:
        if self.owner.state.main_view != "editor":
            return
        reducer.update_editor_content(self.owner.state, self.owner.layout.editor.text)
        self.owner.refresh_views()

    def on_event(self, event_name: str, session_id: str, payload: Dict[str, object]) -> None:
        snapshot = payload.get("session_snapshot")
        if isinstance(snapshot, dict):
            reducer.set_snapshot(self.owner.state, snapshot)
        if event_name == "turn_started":
            reducer.close_stream(self.owner.state)
            reducer.update_snapshot(self.owner.state, status="running", last_error=None)
        elif event_name == "session_status":
            pass
        elif event_name == "assistant_delta":
            reducer.update_snapshot(self.owner.state, status="running")
            reducer.append_delta(self.owner.state, str(payload.get("text") or ""))
        elif event_name == "reasoning_delta":
            reducer.append_line(self.owner.state, "[thinking] %s" % (payload.get("text") or ""))
        elif event_name == "thinking_state":
            if payload.get("active"):
                reducer.append_line(self.owner.state, "[thinking] 模型正在思考...")
        elif event_name == "tool_started":
            reducer.close_stream(self.owner.state)
            reducer.update_snapshot(self.owner.state, status="running")
            reducer.append_line(
                self.owner.state,
                "[tool] %s %s" % (payload.get("tool_name") or "", payload.get("arguments") or {}),
            )
        elif event_name == "tool_finished":
            reducer.close_stream(self.owner.state)
            reducer.update_snapshot(self.owner.state, status="running")
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            if payload.get("tool_name") == "switch_mode" and data.get("to_mode"):
                reducer.update_snapshot(
                    self.owner.state, current_mode=str(data.get("to_mode") or "")
                )
            if payload.get("tool_name") == "ask_user" and data.get("mode"):
                reducer.update_snapshot(
                    self.owner.state, current_mode=str(data.get("mode") or "")
                )
            reducer.append_line(self.owner.state, format_observation_line(payload))
        elif event_name == "permission_required":
            permission = payload.get("permission") or {}
            if isinstance(permission, dict):
                reducer.set_pending_interaction(self.owner.state, permission)
                reducer.close_stream(self.owner.state)
                reducer.update_snapshot(
                    self.owner.state,
                    status="waiting_permission",
                    pending_interaction=permission,
                    pending_interaction_valid=True,
                )
                reducer.append_line(
                    self.owner.state, "[permission] %s" % (permission.get("reason") or "需要确认")
                )
                self.refresh_inspector(self.owner.state.inspector.tab)
        elif event_name == "user_input_required":
            request = payload.get("user_input") or {}
            if isinstance(request, dict):
                reducer.set_pending_interaction(self.owner.state, request)
                reducer.close_stream(self.owner.state)
                reducer.update_snapshot(
                    self.owner.state,
                    status="waiting_user_input",
                    pending_interaction=request,
                    pending_interaction_valid=True,
                )
                questions = request.get("questions") or []
                question = questions[0] if questions and isinstance(questions[0], dict) else {}
                reducer.append_line(
                    self.owner.state,
                    "[question] %s" % (question.get("question") or "需要用户回答"),
                )
                self.refresh_inspector(self.owner.state.inspector.tab)
        elif event_name == "session_finished":
            reducer.close_stream(self.owner.state)
            reducer.set_pending_interaction(self.owner.state, None)
            snapshot = payload.get("session_snapshot")
            if isinstance(snapshot, dict):
                reducer.set_snapshot(self.owner.state, snapshot)
            else:
                reducer.update_snapshot(
                    self.owner.state,
                    status="idle",
                    pending_interaction=None,
                    pending_interaction_valid=False,
                )
            reducer.set_last_error(self.owner.state, "")
            self.refresh_workspace_snapshot()
            self.refresh_sessions()
            self.refresh_tasks()
            self.refresh_artifacts()
            self.reload_timeline()
        elif event_name == "session_resumed":
            reducer.set_last_error(self.owner.state, "")
            self.refresh_sessions()
            self.refresh_tasks()
            self.reload_timeline()
        elif event_name == "session_created":
            self.refresh_sessions()
            self.refresh_tasks()
        elif event_name == "session_error":
            reducer.close_stream(self.owner.state)
            reducer.set_last_error(self.owner.state, str(payload.get("error") or ""))
            reducer.set_pending_interaction(self.owner.state, None)
            reducer.update_snapshot(
                self.owner.state,
                status="error",
                last_error=self.owner.state.session.last_error,
                pending_interaction=None,
                pending_interaction_valid=False,
            )
            reducer.append_line(
                self.owner.state, "[error] %s" % self.owner.state.session.last_error
            )
        elif event_name == "context_compacted":
            reducer.set_context_event(self.owner.state, payload)
            reducer.append_line(self.owner.state, format_context_line(payload))
        self.refresh_inspector(self.owner.state.inspector.tab)
        self.owner.refresh_views()

    def refresh_workspace_snapshot(self) -> None:
        snapshot = self.owner.workspace_service.snapshot()
        session_id = self.owner.state.session.current_session_id
        snapshot["tasks"] = (
            self.owner.session_service.list_tasks(session_id=session_id).get("tasks") or []
        )
        reducer.set_workspace_snapshot(self.owner.state, snapshot)

    def refresh_sessions(self) -> None:
        items = self.owner.session_service.list_sessions(self.owner.state.session_limit)
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
        payload = self.owner.session_service.list_tasks(session_id=session_id)
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

    def refresh_artifacts(self) -> None:
        items = []
        for item in self.owner.artifact_service.list_items(limit=20):
            if not isinstance(item, dict):
                continue
            items.append(
                ArtifactRow(
                    path=str(item.get("path") or ""),
                    tool_name=str(item.get("tool_name") or ""),
                    field_name=str(item.get("field_name") or ""),
                    kind=str(item.get("kind") or ""),
                    created_at=str(item.get("created_at") or ""),
                )
            )
        reducer.set_artifact_items(self.owner.state, items)

    def refresh_explorer(self, tab: str, root: str = ".") -> None:
        tab_name = (tab or "workspace").lower()
        if tab_name == "sessions":
            self.refresh_sessions()
            return
        if tab_name == "tasks":
            self.refresh_tasks()
            return
        payload = self.owner.workspace_service.tree(path=root, max_depth=3, limit=200)
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
        self.current_summary = self.owner.session_service.load_summary(
            str(self.owner.state.session.current_snapshot.get("summary_ref") or "")
        )

    def reload_timeline(self) -> None:
        session_id = self.owner.state.session.current_session_id
        payload = self.owner.timeline_service.load(
            session_id, limit=self.owner.state.transcript_limit
        )
        self.latest_assistant_reply = str(
            payload.get("latest_assistant_reply") or self.latest_assistant_reply or ""
        )
        activities = payload.get("activities") or []
        if activities:
            self.owner.state.timeline.lines = format_activity_records(activities)
            self.owner.state.timeline.stream_text = ""
            reducer.trim_timeline(self.owner.state)
