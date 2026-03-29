from __future__ import annotations


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
            lines.append("[tool] %s %s" % (payload.get("tool_name") or "", payload.get("arguments") or {}))
        elif event == "tool_finished":
            lines.append(format_observation_line(payload))
        elif event == "permission_required":
            permission = payload.get("permission") if isinstance(payload.get("permission"), dict) else {}
            lines.append("[permission] %s" % (permission.get("reason") or "需要确认"))
        elif event == "context_compacted":
            lines.append(format_context_line(payload))
        elif event == "session_error":
            lines.append("[error] %s" % str(payload.get("error") or ""))
        elif event == "session_resumed":
            lines.append("[system] 会话已恢复")
        elif event == "session_created":
            snapshot = payload.get("session_snapshot") if isinstance(payload.get("session_snapshot"), dict) else {}
            lines.append("[system] 已创建会话 %s" % (snapshot.get("session_id") or ""))
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
