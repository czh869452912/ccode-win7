from __future__ import annotations

from embedagent.harness.contracts import ExecutionPhase


def advance_phase(current_phase, artifact_flags, discipline_value):
    del discipline_value
    flags = dict(artifact_flags or {})
    if current_phase == ExecutionPhase.UNDERSTAND and flags.get("contract_ready"):
        return ExecutionPhase.CONTRACT
    if current_phase == ExecutionPhase.CONTRACT and flags.get("implementation_ready"):
        return ExecutionPhase.IMPLEMENT
    if current_phase == ExecutionPhase.IMPLEMENT and flags.get("check_result_ready"):
        return ExecutionPhase.CHECK
    if current_phase == ExecutionPhase.CHECK and flags.get("check_passed"):
        return ExecutionPhase.HANDOFF
    return current_phase
