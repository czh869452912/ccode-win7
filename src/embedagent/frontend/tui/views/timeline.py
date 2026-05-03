from __future__ import annotations

from typing import Any, Dict, List, Optional


class FlatTimelineView(object):
    """Render a flat timeline of items for the conversation UI."""

    def __init__(self, console=None):
        self.console = console
        self._items = []
        self._current_interaction = None

    def update(self, timeline_data):
        """Update with new timeline data from build_flat_timeline()."""
        self._items = list(timeline_data.get("items") or [])
        self._current_interaction = timeline_data.get("current_interaction")

    def render(self):
        """Render the flat timeline as rich console output."""
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        if not self._items:
            return Panel("No conversation yet", title="Timeline")

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("content", ratio=1)

        for item in self._items:
            rendered = self._render_item(item)
            if rendered:
                table.add_row(rendered)

        return Panel(table, title="Conversation")

    def _render_item(self, item):
        """Render a single timeline item based on its type."""
        item_type = item.get("type", "")
        if item_type == "user":
            return self._render_user_item(item)
        elif item_type == "assistant":
            return self._render_assistant_item(item)
        elif item_type == "tool_use":
            return self._render_tool_use_item(item)
        elif item_type == "tool_result":
            return self._render_tool_result_item(item)
        elif item_type == "command_execution":
            return self._render_command_execution_item(item)
        elif item_type == "file_change":
            return self._render_file_change_item(item)
        elif item_type == "interaction":
            return self._render_interaction_item(item)
        elif item_type == "compact":
            return self._render_compact_item(item)
        return None

    def _render_user_item(self, item):
        from rich.text import Text

        text = Text()
        text.append("user ", style="bold cyan")
        text.append(item.get("content", ""), style="cyan")
        return text

    def _render_assistant_item(self, item):
        from rich.text import Text

        text = Text()
        text.append("assistant ", style="bold green")
        text.append(item.get("content", ""), style="green")
        if item.get("reasoning"):
            text.append("\n")
            text.append("Reasoning: " + item["reasoning"], style="dim")
        return text

    def _render_tool_use_item(self, item):
        from rich.panel import Panel
        from rich.text import Text

        tool_name = item.get("tool_name", "")
        arguments = item.get("arguments", {})
        status = item.get("status", "started")

        text = Text()
        text.append("tool ", style="bold yellow")
        text.append(tool_name, style="bold yellow")
        text.append(" (" + status + ")", style="dim")
        if arguments:
            text.append("\n")
            text.append(str(arguments), style="dim")

        return Panel(text, border_style="yellow", padding=(0, 1))

    def _render_tool_result_item(self, item):
        from rich.panel import Panel
        from rich.text import Text

        status = item.get("status", "")
        data = item.get("data")
        error = item.get("error", "")

        text = Text()
        if status == "success":
            text.append("ok ", style="bold green")
            text.append(str(data) if data is not None else "Done", style="green")
        else:
            text.append("fail ", style="bold red")
            text.append(error or str(data) or "Failed", style="red")

        return Panel(
            text,
            border_style="green" if status == "success" else "red",
            padding=(0, 1),
        )

    def _render_command_execution_item(self, item):
        from rich.panel import Panel
        from rich.text import Text

        content = item.get("content", "")
        status = item.get("status", "")

        text = Text()
        text.append("cmd ", style="bold blue")
        text.append("Command Output", style="bold blue")
        if content:
            text.append("\n")
            text.append(content, style="dim")

        style = "blue" if status in ("running", "started") else "green"
        return Panel(text, border_style=style, padding=(0, 1))

    def _render_file_change_item(self, item):
        """Render file change as inline diff."""
        from embedagent.frontend.tui.views.diff import DiffView

        diff_view = DiffView()
        old_text = item.get("old_text", "")
        new_text = item.get("new_text", "")
        filename = item.get("filename", "")
        return diff_view.render_inline(old_text, new_text, filename)

    def _render_interaction_item(self, item):
        from rich.panel import Panel
        from rich.text import Text

        kind = item.get("kind", "")
        content = item.get("content", "")

        text = Text()
        text.append("interaction ", style="bold magenta")
        text.append(kind, style="bold magenta")
        if content:
            text.append("\n")
            text.append(content, style="dim")

        return Panel(text, border_style="magenta", padding=(0, 1))

    def _render_compact_item(self, item):
        from rich.panel import Panel
        from rich.text import Text
        summary = item.get("summary_text", "")
        count = item.get("compacted_turn_count", 0)

        text = Text()
        text.append("Compacted: ", style="bold dim")
        text.append("Compacted %d turns" % count, style="dim")
        if summary:
            text.append("\n")
            text.append(summary, style="dim")

        return Panel(text, border_style="dim", padding=(0, 1))

    def update_command_output(self, item_id: str, text: str) -> bool:
        """Append output text to a command_execution item and mark it running."""
        for item in self._items:
            if item.get("id") == item_id and item.get("type") == "command_execution":
                existing = item.get("content", "")
                item["content"] = existing + text
                item["status"] = "running"
                return True
        return False

    def mark_command_complete(self, item_id: str) -> bool:
        """Mark a command_execution item as completed."""
        for item in self._items:
            if item.get("id") == item_id and item.get("type") == "command_execution":
                item["status"] = "completed"
                return True
        return False

    def update_command_output(self, item_id, text):
        """Append command output text to a command_execution item by id."""
        for item in self._items:
            if item.get("id") == item_id and item.get("type") == "command_execution":
                current = item.get("content", "")
                item["content"] = current + text
                item["status"] = "running"
                return True
        return False

    def mark_command_complete(self, item_id):
        """Mark a command_execution item as completed by id."""
        for item in self._items:
            if item.get("id") == item_id and item.get("type") == "command_execution":
                item["status"] = "completed"
                return True
        return False

    def update_command_output(self, item_id, chunk):
        """Append output chunk to a command_execution item."""
        for item in self._items:
            if item.get("id") == item_id and item.get("type") == "command_execution":
                current = item.get("content", "")
                item["content"] = current + chunk
                item["status"] = "running"
                return True
        return False

    def mark_command_complete(self, item_id, final_status="completed"):
        """Mark a command execution as completed."""
        for item in self._items:
            if item.get("id") == item_id and item.get("type") == "command_execution":
                item["status"] = final_status
                return True
        return False


class TimelineView(object):
    """Timeline view that delegates to FlatTimelineView for flat item data."""

    def __init__(self, console=None):
        self._flat_view = FlatTimelineView(console=console)
        self._legacy_data = None

    def update(self, timeline_data):
        """Update timeline view with either flat or nested timeline data."""
        if timeline_data and "items" in timeline_data:
            self._legacy_data = None
            self._flat_view.update(timeline_data)
        else:
            self._legacy_data = timeline_data

    def render(self):
        """Render timeline, delegating to flat view when items are present."""
        if self._legacy_data is None:
            return self._flat_view.render()
        from rich.panel import Panel

        return Panel("Legacy timeline view", title="Timeline")


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
            lines.append("[permission] %s" % (permission.get("reason") or "\u9700\u8981\u786e\u8ba4"))
        elif event == "user_input_required":
            request = (
                payload.get("user_input") if isinstance(payload.get("user_input"), dict) else {}
            )
            lines.append("[question] %s" % (request.get("question") or "\u9700\u8981\u7528\u6237\u56de\u7b54"))
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
            lines.append("[system] \u5df2\u521b\u5efa\u4f1a\u8bdd %s" % (snapshot.get("session_id") or ""))
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
