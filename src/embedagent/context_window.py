from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class ContextWindowState(object):
    """Safe diagnostic state for one compact boundary's context window."""

    trigger: str = ""
    phase: str = ""
    context_window_generation: int = 0

    @classmethod
    def from_pipeline_steps(
        cls, pipeline_steps: List[str], existing_boundary_count: int
    ) -> "ContextWindowState":
        steps = set(str(item or "") for item in list(pipeline_steps or []))
        trigger = ""
        if "auto_compact_threshold" in steps:
            trigger = "auto_threshold"
        elif "reactive_compact_retry" in steps:
            trigger = "reactive_retry"
        phase = ""
        if trigger == "reactive_retry":
            phase = "provider_retry"
        elif trigger:
            phase = "pre_provider"
        generation = int(existing_boundary_count or 0) + 1 if trigger else 0
        return cls(
            trigger=trigger,
            phase=phase,
            context_window_generation=generation,
        )

    def to_boundary_fields(self) -> Dict[str, Any]:
        if not self.trigger:
            return {}
        return {
            "trigger": self.trigger,
            "phase": self.phase,
            "context_window_generation": int(self.context_window_generation or 0),
        }

    def extend_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(metadata or {})
        result.update(self.to_boundary_fields())
        return result
