from __future__ import annotations

from embedagent.harness.prompt_stack import build_prompt_units
from embedagent.harness.registry import build_default_registry
from embedagent.harness.task_graph import TaskGraph
from embedagent.tooling.packs import pack_tool_names


class HarnessRunner(object):
    def __init__(self, registry=None, prompt_builder=None):
        self.registry = registry or build_default_registry()
        self.prompt_builder = prompt_builder or build_prompt_units

    def build_mode_units(self, mode_name, runtime_nudges=None, discipline_override=None):
        mode = self.registry.get(str(mode_name or ""))
        if mode is None:
            return []
        discipline_label = str(discipline_override or mode.default_discipline.value)
        if mode.slug == "debug":
            pack_name = "debug_lite"
        elif mode.slug == "build":
            pack_name = "build_lite"
        elif mode.slug == "verify":
            pack_name = "verify"
        else:
            pack_name = "core"
        if discipline_label == "full_spec_tdd":
            track = mode.full_track
        else:
            track = mode.lite_track
        checklist_lines = ["[ ] %s" % phase.value for phase in track]
        tool_prompt_lines = [
            "Core pack: %s" % ", ".join(pack_tool_names(pack_name)),
        ]
        task_graph = TaskGraph.for_mode(mode.slug, discipline_label)
        task_summary = task_graph.render_summary()
        units = self.prompt_builder(
            base_prompt="",
            mode_name=mode.slug,
            discipline_label=discipline_label,
            checklist_lines=checklist_lines,
            tool_prompt_lines=tool_prompt_lines + ["Tasks:", task_summary],
            runtime_nudges=list(runtime_nudges or []),
        )
        return [item for item in units if str(item or "").strip()]
