"""
TUI frontend adapter for canonical hosted session events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from embedagent_protocol import SessionEventEnvelope

if TYPE_CHECKING:
    from embedagent.frontend.tui.app import TerminalApp


class TUIFrontend(object):
    def __init__(self, app: "TerminalApp", assembler=None):
        del assembler
        self.app = app

    def refresh_timeline(self) -> None:
        self.app.refresh_views()

    def on_session_event(self, envelope: SessionEventEnvelope) -> None:
        from embedagent.frontend.tui import reducer
        from embedagent.frontend.tui.views.timeline import (
            format_context_line,
            format_observation_line,
        )

        event_kind = envelope.event_kind
        payload = dict(envelope.payload)

        if event_kind == "assistant.delta":
            reducer.append_delta(self.app.state, str(payload.get("text") or ""))
        elif event_kind == "reasoning.delta":
            reducer.append_line(
                self.app.state,
                "[thinking] %s" % str(payload.get("text") or ""),
            )
        elif event_kind == "thinking.state":
            if bool(payload.get("active")):
                reducer.append_line(self.app.state, "[thinking] 模型正在思考...")
        elif event_kind == "tool.started":
            arguments = self._public_arguments(payload.get("arguments"))
            reducer.append_line(
                self.app.state,
                "[tool] %s %s" % (str(payload.get("tool_name") or ""), arguments),
            )
        elif event_kind == "tool.finished":
            failure = payload.get("failure") if isinstance(payload.get("failure"), dict) else {}
            observation = {
                "tool_name": str(payload.get("tool_name") or ""),
                "success": bool(payload.get("success")),
                "data": payload.get("data"),
                "error": str(payload.get("error") or failure.get("message") or ""),
            }
            reducer.append_line(self.app.state, format_observation_line(observation))
        elif event_kind in ("session.status", "session.finished", "session.error"):
            self._apply_session_snapshot(payload, render_error=event_kind != "session.error")
            if event_kind == "session.error":
                snapshot = payload.get("session_snapshot")
                snapshot_error = snapshot.get("last_error") if isinstance(snapshot, dict) else ""
                message = str(payload.get("error") or snapshot_error or "")
                if message:
                    reducer.set_last_error(self.app.state, message)
                    reducer.append_line(self.app.state, "[error] %s" % message)
        elif event_kind == "context.compacted":
            reducer.set_context_event(self.app.state, payload)
            reducer.append_line(self.app.state, format_context_line(payload))
        elif event_kind == "command.result":
            reducer.append_line(
                self.app.state,
                "[command] %s" % str(payload.get("message") or ""),
            )
        elif event_kind == "plan.updated":
            plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
            reducer.append_line(
                self.app.state,
                "[plan] %s" % str(plan.get("title") or "Current Plan"),
            )
        elif event_kind in ("approval.requested", "user-input.requested"):
            reducer.set_pending_interaction(self.app.state, payload)
        elif event_kind in ("approval.resolved", "user-input.resolved"):
            reducer.set_pending_interaction(self.app.state, None)

        self.app.refresh_views()

    def _apply_session_snapshot(self, payload: Dict[str, Any], render_error: bool = True) -> None:
        from embedagent.frontend.tui import reducer

        snapshot = (
            dict(payload.get("session_snapshot") or {})
            if isinstance(payload.get("session_snapshot"), dict)
            else {}
        )
        if not snapshot:
            return
        pending = (
            dict(snapshot.get("pending_interaction") or {})
            if bool(snapshot.get("pending_interaction_valid"))
            and isinstance(snapshot.get("pending_interaction"), dict)
            else None
        )
        reducer.set_pending_interaction(self.app.state, pending)
        reducer.update_snapshot(
            self.app.state,
            **snapshot,
        )
        if render_error and snapshot.get("last_error"):
            message = str(snapshot.get("last_error") or "")
            reducer.set_last_error(self.app.state, message)
            reducer.append_line(self.app.state, "[error] %s" % message)

    @staticmethod
    def _public_arguments(value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        return {key: item for key, item in value.items() if not str(key).startswith("_")}
