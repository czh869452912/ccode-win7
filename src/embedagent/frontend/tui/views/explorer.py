from __future__ import annotations

from embedagent.frontend.tui.state import TerminalState


def build_explorer_text(state: TerminalState) -> str:
    lines = ["Explorer"]
    lines.append("tab=%s  root=%s" % (state.explorer.tab, state.explorer.root))
    lines.append("")
    if not state.explorer.items:
        lines.append("当前没有可展示的条目。")
        return "\n".join(lines)
    for index, item in enumerate(state.explorer.items):
        prefix = ">" if index == state.explorer.selection else " "
        detail = ("  %s" % item.detail) if item.detail else ""
        lines.append("%s %s" % (prefix, item.label))
        if detail:
            lines.append(detail)
    return "\n".join(lines)
