from __future__ import annotations

import json
from typing import Any, Callable, Dict

from embedagent.frontend.tui.state import ContributionState


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True)


def _file_reference(state: ContributionState) -> str:
    lines = [state.label]
    for item in state.data.get("items") or []:
        if not isinstance(item, dict):
            continue
        depth = max(0, int(item.get("depth") or 0))
        marker = "/" if item.get("kind") == "dir" else ""
        lines.append("  " * depth + str(item.get("path") or "") + marker)
    return "\n".join(lines)


def _generic(state: ContributionState) -> str:
    if not state.data:
        return state.label
    return state.label + "\n\n" + _json_text(state.data)


CONTRIBUTION_RENDERERS = {
    "file_reference": _file_reference,
    "terminal": _generic,
    "source_control": _generic,
    "preview": _generic,
    "workflow_summary": _generic,
    "inline_diff": _generic,
}  # type: Dict[str, Callable[[ContributionState], str]]


def render_contribution(state: ContributionState) -> str:
    renderer = CONTRIBUTION_RENDERERS.get(state.renderer_key, _generic)
    return renderer(state)
