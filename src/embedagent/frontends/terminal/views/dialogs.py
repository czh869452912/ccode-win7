from __future__ import annotations

from embedagent.frontends.terminal.state import TerminalState


def build_help_text(state: TerminalState) -> str:
    lines = ["Help"]
    lines.append("")
    lines.append("Commands")
    lines.append("/help")
    lines.append("/new [mode]")
    lines.append("/resume latest|selected|<session_id>")
    lines.append("/workspace [path]")
    lines.append("/sessions")
    lines.append("/todos")
    lines.append("/artifacts")
    lines.append("/artifact <ref>")
    lines.append("/open <path>")
    lines.append("/edit <path>")
    lines.append("/save")
    lines.append("/explorer <workspace|sessions|todos>")
    lines.append("/inspector <status|plan|artifacts|help|snapshot|diff>")
    lines.append("/follow <on|off>")
    lines.append("/mode <name>")
    lines.append("/quit")
    lines.append("")
    lines.append("Keys")
    lines.append("Tab / Shift-Tab switch focus")
    lines.append("Ctrl-Up / Ctrl-Down move explorer selection")
    lines.append("F1 help  F2 new  F3 resume latest")
    lines.append("F4 sessions  F5 activate selection")
    lines.append("F6 snapshot  F7 preview selected")
    lines.append("F8 edit selected  F9 artifacts")
    lines.append("F10 follow output  Ctrl-S save editor")
    if state.session.pending_permission is not None:
        lines.append("")
        lines.append("Permission")
        lines.append("输入 y / n 处理当前确认。")
    return "\n".join(lines)
