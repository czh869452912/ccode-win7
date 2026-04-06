from __future__ import annotations

from embedagent.harness.contracts import (
    DisciplineProfile,
    ExecutionPhase,
    ModeDefinition,
)


def build_default_registry():
    return {
        "build": ModeDefinition(
            slug="build",
            default_discipline=DisciplineProfile.LITE_SPEC_TDD,
            lite_track=[
                ExecutionPhase.UNDERSTAND,
                ExecutionPhase.CONTRACT,
                ExecutionPhase.IMPLEMENT,
                ExecutionPhase.CHECK,
                ExecutionPhase.HANDOFF,
            ],
            full_track=[
                ExecutionPhase.UNDERSTAND,
                ExecutionPhase.CONTRACT,
                ExecutionPhase.TEST_DESIGN,
                ExecutionPhase.IMPLEMENT,
                ExecutionPhase.CHECK,
                ExecutionPhase.REPAIR,
                ExecutionPhase.HANDOFF,
            ],
        ),
        "verify": ModeDefinition(
            slug="verify",
            default_discipline=DisciplineProfile.LITE_SPEC_TDD,
            lite_track=[
                ExecutionPhase.SELECT_RECIPE,
                ExecutionPhase.EXECUTE,
                ExecutionPhase.SUMMARIZE,
            ],
            full_track=[
                ExecutionPhase.SELECT_RECIPE,
                ExecutionPhase.EXECUTE,
                ExecutionPhase.SUMMARIZE,
            ],
            readonly_mode=True,
        ),
    }
