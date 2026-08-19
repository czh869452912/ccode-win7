from __future__ import annotations

from typing import Any, Dict, List, Optional


def _display_transition_reason(reason: str) -> str:
    value = str(reason or "").strip()
    mapping = {
        "aborted": "cancelled",
        "guard_stop": "guard",
        "permission_wait": "waiting_permission",
        "permission_required": "waiting_permission",
        "user_input_wait": "waiting_user_input",
        "user_input_required": "waiting_user_input",
    }
    return mapping.get(value, value)


def _normalize_recent_transitions(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        reason = str(entry.get("reason") or entry.get("kind") or "").strip()
        if reason and not str(entry.get("display_reason") or "").strip():
            entry["display_reason"] = _display_transition_reason(reason)
        normalized.append(entry)
    return normalized


def _workflow_state_from_projection(projection: Dict[str, Any]) -> Dict[str, Any]:
    workflow_state = dict(projection.get("workflow_state") or {})
    if not isinstance(workflow_state, dict):
        return {}
    return workflow_state


class SessionSnapshotProjector(object):
    def build_snapshot(
        self,
        state: Any,
        summary: Optional[Dict[str, Any]],
        runtime: Optional[Dict[str, Any]],
        pending_interaction: Optional[Dict[str, Any]] = None,
        harness_context: Optional[Any] = None,
        extension_diagnostics: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        del harness_context
        summary_payload = dict(summary or {})
        runtime_payload = dict(runtime or {})
        context_analysis = dict(summary_payload.get("context_analysis") or {})
        context_usage = dict(context_analysis.get("context_usage") or {})
        recent_transitions = _normalize_recent_transitions(
            list(summary_payload.get("recent_transitions") or [])
        )
        core_projection = dict(getattr(state, "projection", {}) or {})
        workflow_state = _workflow_state_from_projection(core_projection)
        return {
            "session_id": state.session_id,
            "status": state.status,
            "current_mode": state.current_mode,
            "started_at": str(
                summary_payload.get("started_at") or core_projection.get("started_at") or ""
            ),
            "updated_at": str(summary_payload.get("updated_at") or state.updated_at),
            "workflow_state": workflow_state,
            "has_active_plan": bool(state.active_plan_ref),
            "active_plan_ref": state.active_plan_ref,
            "current_command_context": state.current_command_context,
            "last_user_message": str(summary_payload.get("latest_user_message") or ""),
            "last_assistant_message": str(
                summary_payload.get("assistant_last_reply") or state.last_assistant_message or ""
            ),
            "summary_text": str(summary_payload.get("summary_text") or ""),
            "user_goal": str(summary_payload.get("user_goal") or ""),
            "summary_ref": str(summary_payload.get("summary_ref") or state.summary_ref or ""),
            "compact_summary_text": str(summary_payload.get("compact_summary_text") or ""),
            "context_analysis": context_analysis,
            "context_usage": context_usage,
            "compact_boundary_count": int(core_projection.get("compact_boundary_count") or 0),
            "workspace_intelligence": list(summary_payload.get("workspace_intelligence") or []),
            "context_pipeline_steps": list(summary_payload.get("context_pipeline_steps") or []),
            "last_transition_reason": str(summary_payload.get("last_transition_reason") or ""),
            "last_transition_message": str(summary_payload.get("last_transition_message") or ""),
            "last_transition_display_reason": _display_transition_reason(
                str(summary_payload.get("last_transition_reason") or "")
            ),
            "recent_transition_reasons": list(
                summary_payload.get("recent_transition_reasons") or []
            ),
            "recent_transitions": recent_transitions,
            "compact_retry_count": int(summary_payload.get("compact_retry_count") or 0),
            "pending_interaction": (
                dict(pending_interaction) if pending_interaction is not None else None
            ),
            "last_failure": (
                dict(state.last_failure) if isinstance(state.last_failure, dict) else None
            ),
            "restore_stop_reason": state.restore_stop_reason,
            "restore_consumed_event_count": state.restore_consumed_event_count,
            "restore_transcript_event_count": state.restore_transcript_event_count,
            "operation_diagnostics": dict(getattr(state, "operation_diagnostics", {}) or {}),
            "runtime_config": dict(getattr(state, "runtime_config", {}) or {}),
            "compaction_state": dict(getattr(state, "compaction_state", {}) or {}),
            "recovery_state": dict(getattr(state, "recovery_state", {}) or {}),
            "turn_experience": dict(getattr(state, "turn_experience", {}) or {}),
            "pending_interaction_valid": bool(pending_interaction),
            "extension_diagnostics": list(extension_diagnostics or []),
            "runtime_source": str(runtime_payload.get("runtime_source") or ""),
            "bundled_tools_ready": bool(runtime_payload.get("bundled_tools_ready")),
            "fallback_warnings": list(runtime_payload.get("fallback_warnings") or []),
            "runtime_environment": runtime_payload,
        }
