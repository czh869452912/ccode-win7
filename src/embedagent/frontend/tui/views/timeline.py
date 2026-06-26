from __future__ import annotations


class ActivityTimelineView(object):
    """Render session bootstrap activities for the conversation UI."""

    def __init__(self, console=None):
        self.console = console
        self._activities = []

    def update(self, timeline_data):
        self._activities = list(timeline_data.get("activities") or [])

    def render(self):
        from rich.panel import Panel

        lines = format_activity_records(self._activities)
        if not lines:
            return Panel("No conversation yet", title="Timeline")
        return Panel("\n".join(lines), title="Conversation")


class TimelineView(object):
    """Render session bootstrap activities for timeline panels."""

    def __init__(self, console=None):
        self._activity_view = ActivityTimelineView(console=console)

    def update(self, timeline_data):
        self._activity_view.update(timeline_data or {})

    def render(self):
        return self._activity_view.render()


def format_activity_records(records):
    lines = []
    for item in records:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "")
        content = str(item.get("content") or "")
        status = str(item.get("status") or "")
        if kind == "user":
            lines.append("user> %s" % content)
        elif kind == "assistant":
            lines.append("assistant> %s" % content)
        elif kind == "reasoning":
            lines.append("thinking> %s" % content)
        elif kind == "tool":
            tool_name = str(item.get("tool_name") or "tool")
            suffix = (" " + content) if content else ""
            lines.append("tool %s [%s]%s" % (tool_name, status or "unknown", suffix))
        elif kind == "interaction":
            lines.append("interaction [%s] %s" % (status or "pending", content))
        elif kind == "compact":
            lines.append("compact> %s" % content)
    return lines


def format_observation_line(payload):
    tool_name = str(payload.get("tool_name") or "")
    success = bool(payload.get("success"))
    data = payload.get("data")
    error = str(payload.get("error") or "")
    parts = ["[observation] %s success=%s" % (tool_name, success)]
    if isinstance(data, dict):
        if data.get("path"):
            parts.append("path=%s" % data.get("path"))
        if data.get("command"):
            command = str(data.get("command") or "")
            parts.append("cmd=%s" % (command[:80] + ("..." if len(command) > 80 else "")))
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
        if data.get("to_mode"):
            parts.append("to=%s" % data.get("to_mode"))
        if data.get("selected_mode"):
            parts.append("selected_mode=%s" % data.get("selected_mode"))
        if data.get("error_kind"):
            parts.append("kind=%s" % data.get("error_kind"))
    if error:
        parts.append("error=%s" % (error[:80] + ("..." if len(error) > 80 else "")))
    return " ".join(parts)


def format_context_line(payload):
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


def format_timeline_records(records):
    lines = []
    for item in records:
        if not isinstance(item, dict):
            continue
        event = str(item.get("event") or "")
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        if event == "turn_started":
            lines.append("user> %s" % str(payload.get("text") or ""))
        elif event == "tool_started":
            lines.append(
                "[tool] %s %s" % (payload.get("tool_name") or "", payload.get("arguments") or {})
            )
        elif event == "tool_finished":
            lines.append(format_observation_line(payload))
        elif event == "permission_required":
            permission = (
                payload.get("permission") if isinstance(payload.get("permission"), dict) else {}
            )
            lines.append(
                "[permission] %s" % (permission.get("reason") or "\u9700\u8981\u786e\u8ba4")
            )
        elif event == "user_input_required":
            request = (
                payload.get("user_input") if isinstance(payload.get("user_input"), dict) else {}
            )
            lines.append(
                "[question] %s"
                % (request.get("question") or "\u9700\u8981\u7528\u6237\u56de\u7b54")
            )
        elif event == "context_compacted":
            lines.append(format_context_line(payload))
        elif event == "session_error":
            lines.append("[error] %s" % str(payload.get("error") or ""))
        elif event == "session_resumed":
            lines.append("[system] \u4f1a\u8bdd\u5df2\u6062\u590d")
        elif event == "session_created":
            snapshot = (
                payload.get("session_snapshot")
                if isinstance(payload.get("session_snapshot"), dict)
                else {}
            )
            lines.append(
                "[system] \u5df2\u521b\u5efa\u4f1a\u8bdd %s" % (snapshot.get("session_id") or "")
            )
        elif event == "session_finished":
            text = str(payload.get("final_text") or "").strip()
            if text:
                lines.append("assistant> %s" % text)
    return lines


def build_timeline_text(state):
    parts = list(state.timeline.lines)
    if state.timeline.stream_text:
        parts.append(state.timeline.stream_text)
    if state.main_view == "preview" and state.preview_text:
        header = "Preview: %s" % (state.preview_path or "-")
        return header + "\n\n" + state.preview_text
    return "\n".join(parts)
