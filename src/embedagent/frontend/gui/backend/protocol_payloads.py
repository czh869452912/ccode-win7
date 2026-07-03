from __future__ import annotations

from typing import Any, Dict, Optional

from embedagent.modes import DEFAULT_MODE
from embedagent.protocol import (
    AgentApplicationDescriptor,
    AppBootstrap,
    CapabilitySnapshot,
    CommandDescriptor,
    ModeDescriptor,
    PlanSnapshot,
    ThreadDetailSnapshot,
    ThreadShell,
    ToolPresentation,
    WorkflowPackageDescriptor,
)


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


def _normal_mapping(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normal_list(value: Any) -> list:
    return list(value) if isinstance(value, (list, tuple)) else []


def _camel_or_snake(payload: Dict[str, Any], camel: str, snake: str, default: Any = None) -> Any:
    if camel in payload:
        return payload.get(camel, default)
    if snake in payload:
        return payload.get(snake, default)
    return default


def _agent_application_descriptor(
    item: Any,
    active: bool = False,
) -> Optional[AgentApplicationDescriptor]:
    data = _normal_mapping(item)
    app_id = str(
        data.get("applicationId") or data.get("application_id") or data.get("id") or ""
    ).strip()
    if not app_id:
        return None
    return AgentApplicationDescriptor(
        id=app_id,
        label=str(data.get("label") or data.get("name") or app_id),
        profile_id=str(_camel_or_snake(data, "profileId", "profile_id", "") or ""),
        workflow_package_ids=[
            str(value)
            for value in _normal_list(
                _camel_or_snake(data, "workflowPackageIds", "workflow_package_ids", [])
            )
        ],
        active=bool(data.get("active", active)),
        source_type=str(_camel_or_snake(data, "sourceType", "source_type", "") or ""),
        source_id=str(_camel_or_snake(data, "sourceId", "source_id", "") or ""),
        default=bool(data.get("default", False)),
        metadata=dict(data.get("metadata") or {}),
    )


def _protocol_capability_snapshot(payload: Any) -> CapabilitySnapshot:
    data = _normal_mapping(payload)
    modes = []
    for item in _normal_list(data.get("modes")):
        if not isinstance(item, dict):
            continue
        mode_id = str(item.get("id") or item.get("name") or "").strip()
        if not mode_id:
            continue
        modes.append(
            ModeDescriptor(
                id=mode_id,
                label=str(item.get("label") or item.get("name") or mode_id),
                description=str(item.get("description") or ""),
                icon_key=str(_camel_or_snake(item, "iconKey", "icon_key", "") or ""),
                color_token=str(_camel_or_snake(item, "colorToken", "color_token", "") or ""),
                command_id=str(_camel_or_snake(item, "commandId", "command_id", "") or ""),
            )
        )
    commands = []
    for item in _normal_list(data.get("commands")):
        if not isinstance(item, dict):
            continue
        command_id = str(item.get("id") or item.get("name") or "").strip()
        usage = str(item.get("usage") or "").strip()
        if not command_id and not usage:
            continue
        commands.append(
            CommandDescriptor(
                id=command_id or usage,
                label=str(item.get("label") or usage or command_id),
                group=str(item.get("group") or item.get("source_type") or "command"),
                dispatch=dict(item.get("dispatch") or {}),
                shortcut=str(item.get("shortcut") or ""),
                availability=dict(item.get("availability") or {}),
            )
        )
    tools = []
    for item in _normal_list(data.get("tools")):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        tools.append(
            ToolPresentation(
                name=name,
                label=str(item.get("label") or name),
                icon_key=str(_camel_or_snake(item, "iconKey", "icon_key", "") or ""),
                renderer_key=str(
                    _camel_or_snake(item, "rendererKey", "renderer_key", "generic") or "generic"
                ),
                permission_category=str(
                    _camel_or_snake(
                        item,
                        "permissionCategory",
                        "permission_category",
                        "other",
                    )
                    or "other"
                ),
                metadata=dict(item.get("metadata") or {}),
            )
        )
    workflow_packages = []
    workflow_items = data.get("workflowPackages")
    if workflow_items is None:
        workflow_items = data.get("workflow_packages")
    for item in _normal_list(workflow_items):
        if not isinstance(item, dict):
            continue
        package_id = str(item.get("id") or "").strip()
        if not package_id:
            continue
        workflow_packages.append(
            WorkflowPackageDescriptor(
                id=package_id,
                label=str(item.get("label") or package_id),
                active=bool(item.get("active")),
                state=dict(item.get("state") or {}),
                metadata=dict(item.get("metadata") or {}),
            )
        )
    empty_state = data.get("emptyState")
    if empty_state is None:
        empty_state = data.get("empty_state")
    model_profiles = data.get("modelProfiles")
    if model_profiles is None:
        model_profiles = data.get("model_profiles")
    agent_application = data.get("agentApplication")
    if agent_application is None:
        agent_application = data.get("agent_application")
    agent_applications = data.get("agentApplications")
    if agent_applications is None:
        agent_applications = data.get("agent_applications")
    current_agent_application = _agent_application_descriptor(
        agent_application,
        active=True,
    )
    return CapabilitySnapshot(
        modes=modes,
        commands=commands,
        tools=tools,
        workflow_packages=workflow_packages,
        agent_application=current_agent_application,
        agent_applications=[
            descriptor
            for descriptor in [
                _agent_application_descriptor(item) for item in _normal_list(agent_applications)
            ]
            if descriptor is not None
        ],
        resources=_normal_list(data.get("resources")),
        model_profiles=_normal_list(model_profiles),
        empty_state=dict(empty_state or {}),
    )


def serialize_app_bootstrap(payload: Any) -> Dict[str, Any]:
    data = _normal_mapping(payload)
    commands = []
    for item in _normal_list(data.get("commands")):
        if not isinstance(item, dict):
            continue
        command_id = str(item.get("id") or item.get("name") or "").strip()
        if not command_id:
            continue
        commands.append(
            CommandDescriptor(
                id=command_id,
                label=str(item.get("label") or item.get("usage") or command_id),
                group=str(item.get("group") or "app"),
                dispatch=dict(item.get("dispatch") or {}),
                shortcut=str(item.get("shortcut") or ""),
                availability=dict(item.get("availability") or {}),
            )
        )
    bootstrap = AppBootstrap(
        app=dict(data.get("app") or {}),
        workspaces=_normal_list(data.get("workspaces")),
        commands=commands,
        surfaces=_normal_list(data.get("surfaces")),
        diagnostics=dict(data.get("diagnostics") or {}),
    )
    result = bootstrap.to_dict()
    active_workspace = data.get("active_workspace")
    if active_workspace is None:
        active_workspace = data.get("activeWorkspace")
    result.update(
        {
            "active_workspace": (
                dict(active_workspace) if isinstance(active_workspace, dict) else None
            ),
            "has_active_workspace": bool(
                data.get("has_active_workspace") or data.get("hasActiveWorkspace")
            ),
            "capabilities": dict(data.get("capabilities") or {}),
            "settings": dict(data.get("settings") or {}),
            "last_error": str(data.get("last_error") or data.get("lastError") or ""),
        }
    )
    if "removed" in data:
        result["removed"] = bool(data.get("removed"))
    return result


def serialize_session_bootstrap(payload: Any) -> Dict[str, Any]:
    data = _normal_mapping(payload)
    raw_snapshot = data.get("snapshot")
    raw_snapshot_mapping = _normal_mapping(raw_snapshot)
    snapshot_payload = serialize_session_snapshot(data.get("snapshot"))
    session_id = str(snapshot_payload.get("session_id") or data.get("session_id") or "")
    thread = _normal_mapping(data.get("thread"))
    history = _normal_mapping(data.get("history"))
    workflow = raw_snapshot_mapping.get("workflow_state")
    if not isinstance(workflow, dict):
        workflow = _normal_mapping(data.get("workflow"))
    detail = ThreadDetailSnapshot(
        thread=ThreadShell(
            id=session_id,
            title=str(thread.get("title") or snapshot_payload.get("title") or session_id),
            archived=bool(thread.get("archived")),
            current_mode=str(snapshot_payload.get("current_mode") or ""),
            status=str(snapshot_payload.get("status") or ""),
            updated_at=str(
                snapshot_payload.get("updated_at") or snapshot_payload.get("started_at") or ""
            ),
            pending_interaction=bool(snapshot_payload.get("pending_interaction_valid")),
        ),
        snapshot=snapshot_payload,
        activities=_normal_list(history.get("activities")),
        capabilities=_protocol_capability_snapshot(data.get("capabilities")),
        workflow=workflow,
        integrity=dict(history.get("integrity") or {}),
    )
    result = detail.to_dict()
    result["plan"] = serialize_plan_snapshot(data.get("plan"))
    result["permission_context"] = serialize_permission_context(data.get("permission_context"))
    return result


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
        "turn_experience": dict(read_value(snapshot, "turn_experience", {}) or {}),
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


def serialize_interaction_response(
    payload: Any, session_id: str = "", interaction_id: str = ""
) -> Dict[str, Any]:
    response = to_mapping(payload)
    if response is not None and (
        "snapshot" in response or "interaction_id" in response or "interactionId" in response
    ):
        snapshot = response.get("snapshot")
        return {
            "session_id": str(
                response.get("session_id")
                or session_id
                or read_value(snapshot, "session_id", "")
                or ""
            ),
            "interaction_id": str(
                response.get("interaction_id")
                or response.get("interactionId")
                or interaction_id
                or ""
            ),
            "status": str(response.get("status") or "resolved"),
            "snapshot": serialize_session_snapshot(snapshot) if snapshot is not None else None,
        }

    snapshot = payload
    return {
        "session_id": str(session_id or read_value(snapshot, "session_id", "") or ""),
        "interaction_id": str(interaction_id or ""),
        "status": "resolved",
        "snapshot": serialize_session_snapshot(snapshot) if snapshot is not None else None,
    }


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
    data = dict(payload) if isinstance(payload, dict) else {}
    snapshot = _protocol_capability_snapshot(data).to_dict()
    commands = []
    for item in list(data.get("commands") or []):
        if not isinstance(item, dict):
            continue
        usage = str(item.get("usage") or item.get("label") or "").strip()
        name = str(item.get("name") or item.get("id") or usage).strip()
        if not usage or not name:
            continue
        commands.append(
            {
                "id": str(item.get("id") or name),
                "name": name,
                "usage": usage,
                "label": str(item.get("label") or usage),
                "group": str(item.get("group") or item.get("source_type") or "command"),
                "summary": str(item.get("summary") or ""),
                "source_type": str(item.get("source_type") or ""),
                "source_id": str(item.get("source_id") or ""),
                "active": bool(item.get("active", True)),
                "dispatch": dict(item.get("dispatch") or {}),
            }
        )
    snapshot["commands"] = commands
    return snapshot
