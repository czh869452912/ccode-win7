from __future__ import annotations

from embedagent.harness.prompt_stack import build_prompt_units
from embedagent.harness.registry import build_default_registry
from embedagent.tooling.packs import pack_tool_names


class HarnessRunner(object):
    def __init__(self, registry=None, prompt_builder=None):
        self.registry = registry or build_default_registry()
        self.prompt_builder = prompt_builder or build_prompt_units

    def build_mode_units(self, mode_name, runtime_nudges=None):
        mode = self.registry.get(str(mode_name or ""))
        if mode is None:
            return []
        checklist_lines = ["[ ] %s" % phase.value for phase in mode.lite_track]
        tool_prompt_lines = [
            "Core pack: %s" % ", ".join(pack_tool_names("build_lite")),
        ]
        units = self.prompt_builder(
            base_prompt="",
            mode_name=mode.slug,
            discipline_label=mode.default_discipline.value,
            checklist_lines=checklist_lines,
            tool_prompt_lines=tool_prompt_lines,
            runtime_nudges=list(runtime_nudges or []),
        )
        return [item for item in units if str(item or "").strip()]
