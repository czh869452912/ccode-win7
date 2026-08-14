from __future__ import annotations

from typing import Dict

from embedagent_protocol import SessionEventEnvelope

import embedagent.frontend.tui.reducer as reducer
from embedagent.frontend.runtime import RuntimeAction
from embedagent.frontend.runtime.commands import resolve_command
from embedagent.frontend.tui.commands import parse_command
from embedagent.frontend.tui.views.timeline import format_activity_records


class TerminalController(object):
    def __init__(self, owner) -> None:
        self.owner = owner
        self.latest_assistant_reply = ""

    def start(self) -> None:
        self.refresh_sessions()
        if self.owner.resume_reference:
            self.owner.runtime.resume_session(
                self.owner.resume_reference,
                self.owner.initial_mode,
            )
        else:
            self.owner.runtime.create_session(self.owner.initial_mode)
        if self.owner.initial_message:
            self.submit_message(self.owner.initial_message)

    def accept_input(self, buffer) -> bool:
        text = buffer.text.strip()
        buffer.text = ""
        if text:
            self.handle_input(text)
        return False

    def handle_input(self, text: str) -> None:
        pending = self.owner.state.session.pending_interaction
        if pending is not None:
            if pending.get("kind") == "permission":
                self.handle_permission_reply(text)
            elif pending.get("kind") == "user_input":
                self.handle_user_input_reply(text)
            return
        if text.startswith("/"):
            self.handle_command(text)
        else:
            self.submit_message(text)

    def handle_permission_reply(self, text: str) -> None:
        ticket = self.owner.state.session.pending_interaction or {}
        interaction_id = str(ticket.get("interaction_id") or "")
        normalized = text.strip().lower()
        decisions = {"y": "accept", "yes": "accept", "n": "decline", "no": "decline"}
        decision = decisions.get(normalized)
        if not decision:
            reducer.append_line(self.owner.state, "[permission] enter y or n")
            self.owner.refresh_views()
            return
        self.owner.runtime.respond_to_interaction(
            self.owner.state.session.current_session_id,
            interaction_id,
            {"decision": decision},
        )
        reducer.append_line(self.owner.state, "[permission] %s" % decision)
        self.owner.refresh_views()

    def handle_user_input_reply(self, text: str) -> None:
        ticket = self.owner.state.session.pending_interaction or {}
        interaction_id = str(ticket.get("interaction_id") or "")
        answer = text.strip()
        if not answer:
            reducer.append_line(self.owner.state, "[question] answer required")
            self.owner.refresh_views()
            return
        if answer.isdigit():
            questions = ticket.get("questions") or []
            question = questions[0] if questions and isinstance(questions[0], dict) else {}
            for item in question.get("options") or []:
                if isinstance(item, dict) and int(item.get("index") or 0) == int(answer):
                    answer = str(item.get("label") or item.get("value") or item.get("text") or "")
                    break
        self.owner.runtime.respond_to_interaction(
            self.owner.state.session.current_session_id,
            interaction_id,
            {"answers": {"answer": answer}},
        )
        reducer.append_line(self.owner.state, "[question] %s" % answer)
        self.owner.refresh_views()

    def handle_command(self, text: str) -> None:
        parsed = parse_command(text)
        try:
            command = resolve_command(
                self.owner.shell_descriptor,
                parsed.name,
                self._availability(),
            )
            if str(command.dispatch.get("kind") or "") == "session.command":
                reducer.append_line(self.owner.state, "user> %s" % text)
            self.owner.runtime.dispatch_command(
                self.owner.shell_descriptor,
                command.id,
                parsed.args,
                availability=self._availability(),
                default_mode=self.owner.initial_mode,
            )
            self._after_shell_command(command.dispatch)
        except (RuntimeError, ValueError, TypeError) as exc:
            reducer.set_last_error(self.owner.state, str(exc))
            reducer.append_line(self.owner.state, "[error] %s" % exc)
        self.owner.refresh_views()

    def _after_shell_command(self, dispatch: Dict[str, object]) -> None:
        if str(dispatch.get("kind") or "") in (
            "session.create",
            "session.select",
            "session.rename",
            "session.archive",
            "session.fork",
        ):
            self.refresh_sessions()

    def submit_message(self, text: str) -> None:
        session_id = self.owner.state.session.current_session_id
        if not session_id:
            reducer.append_line(self.owner.state, "[error] no active session")
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

    def create_new_session(self, mode=None) -> None:
        self.owner.runtime.create_session(mode or self.owner.initial_mode)
        self.refresh_sessions()
        self.owner.refresh_views()

    def resume_latest_session(self) -> None:
        self.resume_session("latest")

    def resume_session(self, reference: str) -> None:
        self.owner.runtime.resume_session(reference, self.owner.initial_mode)
        self.refresh_sessions()
        self.owner.refresh_views()

    def open_command_palette(self) -> None:
        reducer.show_command_palette(self.owner.state)
        self.owner.refresh_views()

    def close_command_palette(self) -> None:
        reducer.hide_command_palette(self.owner.state)
        self.owner.refresh_views()

    def close_overlay(self) -> None:
        reducer.hide_command_palette(self.owner.state)
        self.owner.state.overlay.active_id = ""
        for contribution in self.owner.state.contributions.values():
            contribution.active = False
        self.owner.refresh_views()

    def execute_shell_command(self, command_id: str) -> None:
        command = self.owner.state.shell.command_by_id(command_id)
        if not command.id:
            return
        try:
            self.owner.runtime.dispatch_command(
                self.owner.shell_descriptor,
                command.id,
                [],
                availability=self._availability(),
                default_mode=self.owner.initial_mode,
            )
            self._after_shell_command(command.dispatch)
        except (RuntimeError, ValueError, TypeError) as exc:
            reducer.set_last_error(self.owner.state, str(exc))
            reducer.append_line(self.owner.state, "[error] %s" % exc)
        self.owner.refresh_views()

    def on_runtime_action(self, action: RuntimeAction) -> None:
        if not isinstance(action, RuntimeAction):
            raise TypeError("action must be a RuntimeAction")
        value = action.to_dict()
        action_type = action.kind
        if action_type == "session_activated":
            self._install_session_bootstrap(value.get("bootstrap"))
            return
        if action_type == "shell_command":
            self._handle_shell_command(value)
            return
        if action_type == "protocol_failed":
            failure = value.get("failure") if isinstance(value.get("failure"), dict) else {}
            message = str(failure.get("message") or failure.get("code") or "protocol failed")
            reducer.set_last_error(self.owner.state, message)
            reducer.append_line(self.owner.state, "[error] %s" % message)
            self.owner.refresh_views()
            return
        if action_type != "session_event":
            return
        envelope = SessionEventEnvelope.from_dict(value.get("event") or {})
        self.owner.frontend.on_session_event(envelope)
        if envelope.event_kind == "session.finished":
            self.refresh_sessions()
            self.refresh_session_projection()
        self.owner.refresh_views()

    def _handle_shell_command(self, action: Dict[str, object]) -> None:
        dispatch = action.get("dispatch") if isinstance(action.get("dispatch"), dict) else {}
        if str(dispatch.get("kind") or "") != "shell.surface":
            return
        surface_id = str(dispatch.get("surface_id") or "")
        for surface in self.owner.shell_descriptor.surfaces:
            if surface.id == surface_id:
                self._activate_shell_surface(surface.to_dict())
                return
        raise ValueError("unknown_shell_surface:%s" % surface_id)

    def _activate_shell_surface(self, value) -> None:
        surface = dict(value or {}) if isinstance(value, dict) else {}
        surface_id = str(surface.get("id") or "")
        renderer_key = str(surface.get("renderer_key") or "")
        if renderer_key == "command_palette":
            reducer.show_command_palette(self.owner.state)
        elif renderer_key == "composer":
            self.owner.application.layout.focus(self.owner.composer)
        elif renderer_key == "interaction":
            self.owner.state.overlay.active_id = "session.interaction"
        else:
            reducer.activate_contribution(self.owner.state, surface_id)
            self._load_contribution(surface_id, renderer_key)
        self.owner.refresh_views()

    def _load_contribution(self, surface_id: str, renderer_key: str) -> None:
        contribution = self.owner.state.contributions.get(surface_id)
        if contribution is None:
            return
        if renderer_key == "file_reference":
            contribution.data = self.owner.workspace_port.list_workspace_tree(
                path=".", max_depth=3, limit=200
            )

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
        self.owner.state.timeline.items = format_activity_records(history.get("activities") or [])
        reducer.trim_timeline(self.owner.state)
        self.latest_assistant_reply = str(
            history.get("latest_assistant_reply") or self.latest_assistant_reply or ""
        )
        self.owner.refresh_views()

    def refresh_sessions(self) -> None:
        self.owner.state.session.session_items = [
            item.to_dict()
            for item in self.owner.runtime.list_sessions(self.owner.state.session_limit)
        ]

    def refresh_session_projection(self) -> None:
        session_id = self.owner.state.session.current_session_id
        if session_id:
            self.owner.runtime.activate_session(session_id, reason="refresh")

    def _availability(self) -> Dict[str, object]:
        status = str(self.owner.state.session.current_snapshot.get("status") or "")
        return {
            "has_session": bool(self.owner.state.session.current_session_id),
            "has_workspace": bool(self.owner.workspace),
            "running": status in ("running", "submitting"),
            "has_interaction": self.owner.state.session.pending_interaction is not None,
        }
