from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class WorkMode(str, Enum):
    EXPLORE = "explore"
    SPEC = "spec"
    BUILD = "build"
    DEBUG = "debug"
    VERIFY = "verify"


class DisciplineProfile(str, Enum):
    FULL_SPEC_TDD = "full_spec_tdd"
    LITE_SPEC_TDD = "lite_spec_tdd"


class ExecutionPhase(str, Enum):
    UNDERSTAND = "understand"
    CONTRACT = "contract"
    TEST_DESIGN = "test_design"
    IMPLEMENT = "implement"
    CHECK = "check"
    REPAIR = "repair"
    HANDOFF = "handoff"
    REPRODUCE = "reproduce"
    ISOLATE = "isolate"
    FAILING_CHECK = "failing_check"
    PATCH = "patch"
    REGRESSION_CHECK = "regression_check"
    SELECT_RECIPE = "select_recipe"
    EXECUTE = "execute"
    SUMMARIZE = "summarize"


@dataclass
class ArtifactState:
    flags: Dict[str, bool] = field(default_factory=dict)


@dataclass
class ModeDefinition:
    slug: str
    default_discipline: DisciplineProfile
    lite_track: List[ExecutionPhase]
    full_track: List[ExecutionPhase]
    readonly_mode: bool = False
