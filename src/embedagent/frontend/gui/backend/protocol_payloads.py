from __future__ import annotations

from typing import Any, Dict, Optional

from embedagent.modes import DEFAULT_MODE
from embedagent.protocol import PlanSnapshot


def to_mapping(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    payload = getattr(value, "__dict__", None)
    if isinstance(payload, dict):
        return dict(payload)
    return None


def read_value(payload: Any, key: str, default: Any = None, aliases: tuple = ()) -> Any:
    if isinstance(payload, dict):
        if key in payload:
            return payload.get(key, default)
        for alias in aliases:
            if alias in payload:
                return payload.get(alias, default)
        return default
    for name in (key,) + tuple(aliases):
        if hasattr(payload, name):
            return getattr(payload, name)
    return default


def read_status_value(snapshot: Any) -> str:
    status = read_value(snapshot, "status", "")
    return str(getattr(status, "value", status) or "")


def serialize_session_snapshot(snapshot: Any) -> Dict[str, Any]:
    pending_interaction = to_mapping(read_value(snapshot, "pending_interaction"))
    runtime_environment = to_mapping(read_value(snapshot, "runtime_environment"))
    pending_interaction_valid = read_value(snapshot, "pending_interaction_valid", None)
    if pending_interaction_valid is None:
        pending_interaction_valid = bool(pending_interaction)
    return {
        "session_id": str(read_value(snapshot, "session_id", "") or ""),
        "status": read_status_value(snapshot),
        "current_mode": str(read_value(snapshot, "current_mode", DEFAULT_MODE) or DEFAULT_MODE),
        "started_at": str(read_value(snapshot, "started_at", "", aliases=("created_at",)) or ""),
        "updated_at": str(read_value(snapshot, "updated_at", "") or ""),
        "workflow_state": str(read_value(snapshot, "workflow_state", "chat") or "chat"),
        "has_active_plan": bool(read_value(snapshot, "has_active_plan", False)),
        "active_plan_ref": str(read_value(snapshot, "active_plan_ref", "") or ""),
        "current_command_context": str(read_value(snapshot, "current_command_context", "") or ""),
        "pending_interaction": pending_interaction,
        "last_error": read_value(snapshot, "last_error"),
        "runtime_source": str(read_value(snapshot, "runtime_source", "") or ""),
        "bundled_tools_ready": bool(read_value(snapshot, "bundled_tools_ready", False)),
        "fallback_warnings": list(read_value(snapshot, "fallback_warnings", []) or []),
        "runtime_environment": runtime_environment,
        "compact_summary_text": str(read_value(snapshot, "compact_summary_text", "") or ""),
        "context_analysis": dict(read_value(snapshot, "context_analysis", {}) or {}),
        "context_usage": dict(read_value(snapshot, "context_usage", {}) or {}),
        "compact_boundary_count": int(read_value(snapshot, "compact_boundary_count", 0) or 0),
        "workspace_intelligence": list(read_value(snapshot, "workspace_intelligence", []) or []),
        "context_pipeline_steps": list(read_value(snapshot, "context_pipeline_steps", []) or []),
        "last_transition_reason": str(read_value(snapshot, "last_transition_reason", "") or ""),
        "last_transition_message": str(read_value(snapshot, "last_transition_message", "") or ""),
        "last_transition_display_reason": str(
            read_value(snapshot, "last_transition_display_reason", "") or ""
        ),
        "recent_transition_reasons": list(
            read_value(snapshot, "recent_transition_reasons", []) or []
        ),
        "recent_transitions": list(read_value(snapshot, "recent_transitions", []) or []),
        "compact_retry_count": int(read_value(snapshot, "compact_retry_count", 0) or 0),
        "pending_interaction_valid": bool(pending_interaction_valid),
        "restore_stop_reason": str(read_value(snapshot, "restore_stop_reason", "") or ""),
        "restore_consumed_event_count": int(
            read_value(snapshot, "restore_consumed_event_count", 0) or 0
        ),
        "restore_transcript_event_count": int(
            read_value(snapshot, "restore_transcript_event_count", 0) or 0
        ),
        "operation_diagnostics": dict(read_value(snapshot, "operation_diagnostics", {}) or {}),
        "runtime_config": dict(read_value(snapshot, "runtime_config", {}) or {}),
        "compaction_state": dict(read_value(snapshot, "compaction_state", {}) or {}),
        "recovery_state": dict(read_value(snapshot, "recovery_state", {}) or {}),
        "current_phase": str(read_value(snapshot, "current_phase", "") or ""),
        "discipline_profile": str(read_value(snapshot, "discipline_profile", "") or ""),
        "current_activity": str(read_value(snapshot, "current_activity", "") or ""),
        "task_summary": str(read_value(snapshot, "task_summary", "") or ""),
        "task_items": list(read_value(snapshot, "task_items", []) or []),
    }


def serialize_session_summary(payload: Any) -> Dict[str, Any]:
    data = dict(payload or {})
    thread = data.get("thread") if isinstance(data.get("thread"), dict) else {}
    safe_thread = {
        "title": str(thread.get("title") or ""),
        "archived": bool(thread.get("archived")),
        "archived_at": str(thread.get("archived_at") or ""),
        "forked_from": str(thread.get("forked_from") or ""),
        "forked_at": str(thread.get("forked_at") or ""),
    }
    return {
        "session_id": str(data.get("session_id") or ""),
        "title": str(data.get("title") or safe_thread.get("title") or ""),
        "current_mode": str(data.get("current_mode") or ""),
        "updated_at": str(data.get("updated_at") or ""),
        "summary_ref": str(data.get("summary_ref") or ""),
        "transcript_ref": str(data.get("transcript_ref") or ""),
        "thread": safe_thread,
    }


def serialize_interaction_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    response = dict(payload or {})
    snapshot = response.get("snapshot")
    if snapshot is not None:
        response["snapshot"] = serialize_session_snapshot(snapshot)
    return response


def serialize_plan_snapshot(plan: Optional[PlanSnapshot]) -> Optional[Dict[str, Any]]:
    if plan is None:
        return None
    return {
        "session_id": plan.session_id,
        "title": plan.title,
        "content": plan.content,
        "updated_at": plan.updated_at,
        "workflow_state": plan.workflow_state,
        "path": plan.path,
        "summary": plan.summary,
    }


def serialize_permission_context(context: Any) -> Dict[str, Any]:
    return {
        "session_id": str(read_value(context, "session_id", "") or ""),
        "rules_path": str(read_value(context, "rules_path", "") or ""),
        "categories": list(read_value(context, "categories", []) or []),
        "rules": list(read_value(context, "rules", []) or []),
        "remembered_categories": list(read_value(context, "remembered_categories", []) or []),
        "auto_approve_all": bool(read_value(context, "auto_approve_all", False)),
        "auto_approve_writes": bool(read_value(context, "auto_approve_writes", False)),
        "auto_approve_commands": bool(read_value(context, "auto_approve_commands", False)),
    }


def serialize_session_capabilities(payload: Any) -> Dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    commands = []
    for item in list(data.get("commands") or []):
        if not isinstance(item, dict):
            continue
        usage = str(item.get("usage") or "").strip()
        name = str(item.get("name") or "").strip()
        if not usage or not name:
            continue
        commands.append(
            {
                "name": name,
                "usage": usage,
                "summary": str(item.get("summary") or ""),
                "source_type": str(item.get("source_type") or ""),
                "source_id": str(item.get("source_id") or ""),
                "active": bool(item.get("active")),
            }
        )
    return {"commands": commands}
