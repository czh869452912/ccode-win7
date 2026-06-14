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


def _workflow_from_session(session: Any) -> Dict[str, Any]:
    workflow_state = getattr(session, "workflow_state", {}) or {}
    if not isinstance(workflow_state, dict):
        return {}
    workflow = workflow_state.get("workflow") or {}
    if not isinstance(workflow, dict):
        return {}
    return dict(workflow)


def _workflow_metadata(workflow: Dict[str, Any]) -> Dict[str, Any]:
    metadata = workflow.get("metadata") or {}
    if not isinstance(metadata, dict):
        return {}
    return dict(metadata)


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
        recent_transitions = _normalize_recent_transitions(
            list(summary_payload.get("recent_transitions") or [])
        )
        workflow = _workflow_from_session(state.session)
        metadata = _workflow_metadata(workflow)
        workflow_items = list(workflow.get("items") or [])
        workflow_phase = str(metadata.get("current_phase") or workflow.get("current_phase") or "")
        workflow_discipline = str(
            metadata.get("discipline_profile") or workflow.get("discipline_profile") or ""
        )
        workflow_summary = str(workflow.get("summary") or "")
        workflow_activity = str(workflow.get("activity") or "")
        workflow_state = getattr(state.session, "workflow_state", {}) or {}
        extensions = {}
        if isinstance(workflow_state, dict):
            raw_extensions = workflow_state.get("extensions") or {}
            if isinstance(raw_extensions, dict):
                extensions = dict(raw_extensions)
        return {
            "session_id": state.session.session_id,
            "status": state.status,
            "current_mode": state.current_mode,
            "started_at": str(summary_payload.get("started_at") or state.session.started_at),
            "updated_at": str(summary_payload.get("updated_at") or state.updated_at),
            "workflow_state": state.workflow_state,
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
            "context_analysis": dict(summary_payload.get("context_analysis") or {}),
            "compact_boundary_count": len(getattr(state.session, "compact_boundaries", []) or []),
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
            "has_pending_permission": state.pending_permission is not None,
            "pending_permission": (
                state.pending_permission.to_dict() if state.pending_permission else None
            ),
            "has_pending_user_input": state.pending_user_input is not None,
            "pending_user_input": (
                state.pending_user_input.to_dict() if state.pending_user_input else None
            ),
            "pending_interaction": (
                dict(pending_interaction) if pending_interaction is not None else None
            ),
            "last_error": state.last_error,
            "restore_stop_reason": state.restore_stop_reason,
            "restore_consumed_event_count": state.restore_consumed_event_count,
            "restore_transcript_event_count": state.restore_transcript_event_count,
            "operation_diagnostics": dict(getattr(state, "operation_diagnostics", {}) or {}),
            "runtime_config": dict(getattr(state, "runtime_config", {}) or {}),
            "compaction_state": dict(getattr(state, "compaction_state", {}) or {}),
            "recovery_state": dict(getattr(state, "recovery_state", {}) or {}),
            "timeline_replay_status": (
                "degraded" if state.restore_stop_reason == "transcript_missing" else "replay"
            ),
            "timeline_first_seq": 0,
            "timeline_last_seq": 0,
            "timeline_integrity": (
                "degraded" if state.restore_stop_reason == "transcript_missing" else "healthy"
            ),
            "pending_interaction_valid": bool(state.pending_permission or state.pending_user_input),
            "current_phase": workflow_phase,
            "discipline_profile": workflow_discipline,
            "current_activity": workflow_activity,
            "task_summary": workflow_summary,
            "task_items": workflow_items,
            "workflow": workflow,
            "extensions": extensions,
            "extension_diagnostics": list(extension_diagnostics or []),
            "runtime_source": str(runtime_payload.get("runtime_source") or ""),
            "bundled_tools_ready": bool(runtime_payload.get("bundled_tools_ready")),
            "fallback_warnings": list(runtime_payload.get("fallback_warnings") or []),
            "runtime_environment": runtime_payload,
        }
