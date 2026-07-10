from __future__ import annotations

from typing import Any, Dict


def _display_rows(phase: str, discipline: str, activity: str):
    rows = []
    for key, label_key, value in (
        ("current_phase", "inspector.currentPhase", phase),
        ("discipline_profile", "inspector.disciplineProfile", discipline),
        ("current_activity", "inspector.currentActivity", activity),
    ):
        text = str(value or "")
        if text:
            rows.append({"key": key, "label_key": label_key, "value": text})
    return rows


def build_c_harness_workflow_projection(graph: Any, context: Any = None) -> Dict[str, Any]:
    summary = str(graph.render_summary())
    items = list(graph.to_items())
    phase = str(getattr(graph, "current_phase", "") or "")
    discipline = str(getattr(graph, "discipline", "") or "")
    activity = ""
    if context is not None:
        summary = str(getattr(context, "task_summary", "") or summary)
        items = list(getattr(context, "task_items", []) or items)
        phase = str(getattr(context, "current_phase", "") or phase)
        discipline = str(getattr(context, "discipline_label", "") or discipline)
        activity = str(getattr(context, "current_activity", "") or "")
    return {
        "id": "c_harness",
        "label": "C Harness",
        "state": "idle" if graph.is_empty() else "active",
        "summary": summary,
        "items": items,
        "activity": activity,
        "metadata": {
            "current_phase": phase,
            "discipline_profile": discipline,
            "display_rows": _display_rows(phase, discipline, activity),
        },
    }
