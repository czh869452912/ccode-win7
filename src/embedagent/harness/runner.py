from __future__ import annotations

from embedagent.harness.contracts import HarnessModeContext
from embedagent.harness.packs import pack_tool_names
from embedagent.harness.phase_engine import advance_until_stable, artifact_flags_from_observations
from embedagent.harness.prompt_stack import build_prompt_units
from embedagent.harness.registry import build_default_registry
from embedagent.harness.task_graph import TaskGraph


class HarnessRunner(object):
    def __init__(self, registry=None, prompt_builder=None):
        self.registry = registry or build_default_registry()
        self.prompt_builder = prompt_builder or build_prompt_units

    def _pack_name_for(self, mode_slug):
        if mode_slug == "debug":
            return "debug_lite"
        if mode_slug == "build":
            return "build_lite"
        if mode_slug == "verify":
            return "verify"
        return "core"

    def describe_mode(
        self,
        mode_name,
        runtime_nudges=None,
        discipline_override=None,
        current_phase="",
        observations=None,
    ):
        mode = self.registry.get(str(mode_name or ""))
        if mode is None:
            return None
        discipline_label = str(discipline_override or mode.default_discipline.value)
        if discipline_label == "full_spec_tdd":
            track = mode.full_track
        else:
            track = mode.lite_track
        phase_value = str(current_phase or (track[0].value if track else ""))
        flags = artifact_flags_from_observations(observations)
        if flags:
            next_phase = advance_until_stable(phase_value, flags, discipline_label)
            phase_value = str(getattr(next_phase, "value", next_phase) or phase_value)
        checklist_lines = ["[ ] %s" % phase.value for phase in track]
        tool_prompt_lines = [
            "Core pack: %s" % ", ".join(pack_tool_names(self._pack_name_for(mode.slug))),
        ]
        task_graph = TaskGraph.for_mode(
            mode.slug,
            discipline_label,
            track=track,
            current_phase=phase_value,
        )
        task_summary = task_graph.render_summary()
        units = self.prompt_builder(
            base_prompt="",
            mode_name=mode.slug,
            discipline_label=discipline_label,
            checklist_lines=checklist_lines,
            tool_prompt_lines=tool_prompt_lines + ["Tasks:", task_summary],
            runtime_nudges=list(runtime_nudges or []),
        )
        return HarnessModeContext(
            mode_name=mode.slug,
            discipline_label=discipline_label,
            pack_name=self._pack_name_for(mode.slug),
            current_phase=phase_value,
            current_activity="%s harness active (%s)" % (mode.slug, phase_value or "idle"),
            task_summary=task_summary,
            track=[phase.value for phase in track],
            task_items=task_graph.to_items(),
            prompt_units=[item for item in units if str(item or "").strip()],
        )

    def build_mode_units(self, mode_name, runtime_nudges=None, discipline_override=None):
        context = self.describe_mode(
            mode_name,
            runtime_nudges=runtime_nudges,
            discipline_override=discipline_override,
        )
        if context is None:
            return []
        return list(context.prompt_units)

    def update_task_graph(
        self,
        graph,
        mode_name,
        observations=None,
        discipline_override=None,
    ):
        current_phase = ""
        if graph is not None and str(getattr(graph, "mode_name", "") or "") == str(mode_name or ""):
            current_phase = str(getattr(graph, "current_phase", "") or "")
        context = self.describe_mode(
            mode_name,
            discipline_override=discipline_override,
            current_phase=current_phase,
            observations=observations,
        )
        if context is None:
            empty = TaskGraph.empty()
            if graph is None:
                return empty
            graph.replace_with(empty)
            return graph
        updated = TaskGraph.for_mode(
            context.mode_name,
            context.discipline_label,
            track=context.track,
            current_phase=context.current_phase,
        )
        if graph is None:
            return updated
        graph.replace_with(updated)
        return graph
