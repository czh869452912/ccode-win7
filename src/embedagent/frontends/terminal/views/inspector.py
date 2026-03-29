from __future__ import annotations

import json

from embedagent.frontends.terminal.state import TerminalState
from embedagent.frontends.terminal.views.dialogs import build_help_text as build_dialog_help_text


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def build_inspector_text(state: TerminalState, summary, latest_reply: str):
    tab = state.inspector.tab
    if tab == "help":
        return build_dialog_help_text(state)
    if tab == "snapshot":
        payload = dict(state.session.current_snapshot)
        if state.session.pending_permission is not None:
            payload["pending_permission"] = state.session.pending_permission
        if state.session.last_context_event:
            payload["last_context_event"] = state.session.last_context_event
        if state.workspace_snapshot:
            payload["workspace_snapshot"] = state.workspace_snapshot
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if tab == "plan":
        lines = ["Plan", ""]
        if latest_reply:
            lines.append(latest_reply)
        else:
            lines.append("当前还没有可展示的 assistant 方案。")
        todos = state.workspace_snapshot.get("todos") if isinstance(state.workspace_snapshot.get("todos"), list) else None
        if todos:
            lines.append("")
            lines.append("Todos")
            for item in todos:
                if not isinstance(item, dict):
                    continue
                prefix = "[x]" if item.get("done") else "[ ]"
                lines.append("%s %s" % (prefix, item.get("content") or ""))
        return "\n".join(lines)
    if tab == "artifacts":
        lines = ["Artifacts", ""]
        if not state.inspector.artifact_items:
            lines.append("当前没有 artifact。")
        else:
            for item in state.inspector.artifact_items:
                lines.append("- %s (%s/%s)" % (item.path, item.tool_name or "-", item.field_name or "-"))
        if state.inspector.selected_artifact_ref:
            lines.append("")
            lines.append("Selected")
            lines.append(state.inspector.selected_artifact_ref)
        return "\n".join(lines)
    if tab == "diff":
        lines = ["Diff", ""]
        if state.editor.warning:
            lines.append("Warning: %s" % state.editor.warning)
            lines.append("")
        lines.append(state.editor.diff_preview or "当前没有 diff 预览。")
        return "\n".join(lines)
    lines = ["Session"]
    snapshot = state.session.current_snapshot
    lines.append("- id: %s" % (snapshot.get("session_id") or "-"))
    lines.append("- mode: %s" % (snapshot.get("current_mode") or state.initial_mode))
    lines.append("- status: %s" % (snapshot.get("status") or "-"))
    lines.append("- host: %s" % state.capability.host_mode)
    lines.append("")
    lines.append("Context")
    context_stats = summary.get("context_stats") if isinstance(summary, dict) and isinstance(summary.get("context_stats"), dict) else {}
    for key, value in state.session.last_context_event.items():
        context_stats[key] = value
    lines.append("- recent: %s" % context_stats.get("recent_turns", "-"))
    lines.append("- summarized: %s" % context_stats.get("summarized_turns", "-"))
    lines.append("- tokens: %s" % context_stats.get("approx_tokens_after", "-"))
    if state.workspace_snapshot:
        git_info = state.workspace_snapshot.get("git") if isinstance(state.workspace_snapshot.get("git"), dict) else {}
        tree_info = state.workspace_snapshot.get("tree") if isinstance(state.workspace_snapshot.get("tree"), dict) else {}
        lines.append("")
        lines.append("Workspace")
        lines.append("- branch: %s" % (git_info.get("branch") or "-"))
        lines.append("- dirty: %s" % (git_info.get("dirty_count") or 0))
        lines.append("- files: %s" % (tree_info.get("file_count") or 0))
        lines.append("- dirs: %s" % (tree_info.get("dir_count") or 0))
    if summary:
        lines.append("")
        lines.append("Work")
        lines.append("- goal: %s" % _truncate_text(str(summary.get("user_goal") or "-"), 84))
        lines.append("- working_set: %s" % (", ".join((summary.get("working_set") or [])[:4]) if summary.get("working_set") else "-"))
        lines.append("- modified: %s" % (", ".join((summary.get("modified_files") or [])[:4]) if summary.get("modified_files") else "-"))
        artifacts = summary.get("recent_artifacts") or []
        lines.append("- artifacts: %s" % len(artifacts))
    if state.session.pending_permission:
        permission = state.session.pending_permission
        lines.append("")
        lines.append("Permission")
        lines.append("- tool: %s" % (permission.get("tool_name") or "-"))
        lines.append("- reason: %s" % _truncate_text(str(permission.get("reason") or "-"), 96))
    if state.session.last_error:
        lines.append("")
        lines.append("Error")
        lines.append("- %s" % _truncate_text(state.session.last_error, 96))
    return "\n".join(lines)


def build_help_text(state: TerminalState) -> str:
    return build_dialog_help_text(state)
