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


def build_timeline_text(state):
    parts = list(state.timeline.items)
    if state.timeline.stream_text:
        parts.append(state.timeline.stream_text)
    return "\n".join(parts)
