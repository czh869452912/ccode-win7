from __future__ import annotations

from embedagent.harness.contracts import ExecutionPhase


def normalize_phase(current_phase):
    if isinstance(current_phase, ExecutionPhase):
        return current_phase
    raw = str(getattr(current_phase, "value", current_phase) or "").strip()
    for item in ExecutionPhase:
        if item.value == raw:
            return item
    return None


def artifact_flags_from_observations(observations):
    flags = {}
    for observation in list(observations or []):
        if observation is None or not getattr(observation, "success", False):
            continue
        tool_name = str(getattr(observation, "tool_name", "") or "")
        data = getattr(observation, "data", {})
        if not isinstance(data, dict):
            data = {}
        if tool_name == "record_failing_evidence":
            flags["failing_evidence_ready"] = True
        if tool_name in ("edit_file", "write_file"):
            flags["implementation_ready"] = True
        if tool_name == "list_recipes":
            flags["recipe_selected"] = True
        if tool_name == "run_recipe":
            flags["execution_started"] = True
            flags["check_result_ready"] = True
            flags["regression_result_ready"] = True
            flags["check_passed"] = bool(getattr(observation, "success", False))
        if tool_name == "report_quality_v2":
            flags["quality_report_ready"] = True
            flags["check_result_ready"] = True
            flags["check_passed"] = bool(data.get("passed"))
    return flags


def advance_phase(current_phase, artifact_flags, discipline_value):
    current_phase = normalize_phase(current_phase)
    if current_phase is None:
        return current_phase
    discipline = str(discipline_value or "")
    flags = dict(artifact_flags or {})
    if current_phase == ExecutionPhase.UNDERSTAND and flags.get("contract_ready"):
        return ExecutionPhase.CONTRACT
    if (
        current_phase == ExecutionPhase.CONTRACT
        and discipline == "full_spec_tdd"
        and flags.get("failing_evidence_ready")
    ):
        return ExecutionPhase.TEST_DESIGN
    if current_phase == ExecutionPhase.CONTRACT and flags.get("implementation_ready"):
        return ExecutionPhase.IMPLEMENT
    if current_phase == ExecutionPhase.IMPLEMENT and flags.get("check_result_ready"):
        return ExecutionPhase.CHECK
    if (
        current_phase == ExecutionPhase.CHECK
        and discipline == "full_spec_tdd"
        and flags.get("check_result_ready")
        and not flags.get("check_passed")
    ):
        return ExecutionPhase.REPAIR
    if current_phase == ExecutionPhase.CHECK and flags.get("check_passed"):
        return ExecutionPhase.HANDOFF
    if current_phase == ExecutionPhase.REPRODUCE and flags.get("failing_evidence_ready"):
        return ExecutionPhase.ISOLATE
    if current_phase == ExecutionPhase.ISOLATE and flags.get("implementation_ready"):
        return ExecutionPhase.PATCH
    if current_phase == ExecutionPhase.PATCH and flags.get("regression_result_ready"):
        return ExecutionPhase.REGRESSION_CHECK
    if current_phase == ExecutionPhase.REGRESSION_CHECK and flags.get("regression_result_ready"):
        if flags.get("check_passed"):
            return ExecutionPhase.HANDOFF
        return ExecutionPhase.PATCH
    if current_phase == ExecutionPhase.SELECT_RECIPE and (flags.get("recipe_selected") or flags.get("execution_started")):
        return ExecutionPhase.EXECUTE
    if current_phase == ExecutionPhase.EXECUTE and flags.get("quality_report_ready"):
        return ExecutionPhase.SUMMARIZE
    return current_phase


def advance_until_stable(current_phase, artifact_flags, discipline_value, max_steps=8):
    phase = normalize_phase(current_phase)
    if phase is None:
        return current_phase
    for _ in range(max(1, int(max_steps or 1))):
        next_phase = normalize_phase(advance_phase(phase, artifact_flags, discipline_value))
        if next_phase is None or next_phase == phase:
            break
        phase = next_phase
    return phase
