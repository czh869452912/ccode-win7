from __future__ import annotations


def build_prompt_units(
    base_prompt,
    mode_name,
    discipline_label,
    checklist_lines,
    tool_prompt_lines,
    runtime_nudges,
):
    mode_context = "\n".join(
        [
            "Mode: %s" % mode_name,
            "Discipline: %s" % discipline_label,
            "Checklist:",
        ]
        + list(checklist_lines or [])
        + ["Tools:"]
        + list(tool_prompt_lines or [])
    )
    runtime_context = "\n".join(list(runtime_nudges or []))
    return [base_prompt, mode_context, runtime_context]
