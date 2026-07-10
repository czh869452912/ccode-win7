from __future__ import annotations

from typing import Any, Dict


def payload_data(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def observation_data(observation: Any) -> Dict[str, Any]:
    return payload_data(getattr(observation, "data", None))


def recipe_action_from_data(data: Any) -> str:
    payload = payload_data(data)
    return str(payload.get("recipe_action") or "").strip().lower()


def recipe_action_from_observation(observation: Any) -> str:
    return recipe_action_from_data(observation_data(observation))


def is_recipe_evidence_data(data: Any) -> bool:
    return bool(recipe_action_from_data(data))


def is_quality_gate_data(data: Any) -> bool:
    payload = payload_data(data)
    if "passed" not in payload:
        return False
    quality_fields = (
        "error_count",
        "warning_count",
        "test_failures",
        "reasons",
        "line_coverage",
        "min_line_coverage",
    )
    return any(name in payload for name in quality_fields)


def is_failed_quality_gate_data(data: Any) -> bool:
    payload = payload_data(data)
    return is_quality_gate_data(payload) and not bool(payload.get("passed", False))


def is_quality_gate_observation(observation: Any) -> bool:
    return is_quality_gate_data(observation_data(observation))


def is_failed_quality_gate_observation(observation: Any) -> bool:
    return is_failed_quality_gate_data(observation_data(observation))


def is_diagnostic_observation(observation: Any) -> bool:
    data = observation_data(observation)
    if not data:
        return False
    diagnostics = data.get("diagnostics") if isinstance(data.get("diagnostics"), list) else []
    if diagnostics:
        return True
    if is_failed_quality_gate_data(data):
        return True
    action = recipe_action_from_data(data)
    if action == "test" and isinstance(data.get("test_summary"), dict):
        return True
    if action == "coverage" and isinstance(data.get("coverage_summary"), dict):
        return True
    if action in ("build", "configure", "tidy", "analyze") and getattr(observation, "error", None):
        return True
    return False
