from __future__ import annotations

from embedagent.workflow_packages.c_cpp.contracts import (
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
        "debug": ModeDefinition(
            slug="debug",
            default_discipline=DisciplineProfile.LITE_SPEC_TDD,
            lite_track=[
                ExecutionPhase.REPRODUCE,
                ExecutionPhase.ISOLATE,
                ExecutionPhase.PATCH,
                ExecutionPhase.REGRESSION_CHECK,
                ExecutionPhase.HANDOFF,
            ],
            full_track=[
                ExecutionPhase.REPRODUCE,
                ExecutionPhase.ISOLATE,
                ExecutionPhase.FAILING_CHECK,
                ExecutionPhase.PATCH,
                ExecutionPhase.REGRESSION_CHECK,
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
