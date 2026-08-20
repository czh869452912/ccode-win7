from __future__ import annotations

from typing import Any, Dict, Optional

from embedagent_protocol import (
    AgentApplicationDescriptor,
    AppBootstrap,
    CapabilitySnapshot,
    CommandDescriptor,
    FailureRecord,
    InteractionDescriptor,
    KeybindingDescriptor,
    ModeDescriptor,
    PlanSnapshot,
    SessionBootstrap,
    ShellDescriptor,
    SurfaceDescriptor,
    ThreadShell,
    TimelineItemDescriptor,
    ToolPresentation,
    WorkflowPackageDescriptor,
)
from embedagent_protocol.versions import FRONTEND_PROTOCOL_SCHEMA_VERSION


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


def _capability_records(data: Dict[str, Any], key: str) -> list:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise ValueError("capabilities.%s must be a list" % key)
    if any(not isinstance(item, dict) for item in value):
        raise ValueError("capabilities.%s contains an invalid item" % key)
    return value


def _agent_application_descriptor(
    item: Any,
    active: bool = False,
) -> Optional[AgentApplicationDescriptor]:
    data = _normal_mapping(item)
    if not data:
        return None
    return AgentApplicationDescriptor(
        id=str(data.get("applicationId") or ""),
        label=str(data.get("label") or ""),
        profile_id=str(data.get("profileId") or ""),
        workflow_package_ids=[str(value) for value in _normal_list(data.get("workflowPackageIds"))],
        active=bool(data.get("active", active)),
        source_type=str(data.get("sourceType") or ""),
        source_id=str(data.get("sourceId") or ""),
        default=bool(data.get("default", False)),
        metadata=dict(data.get("metadata") or {}),
    )


def _protocol_capability_snapshot(payload: Any) -> CapabilitySnapshot:
    data = _normal_mapping(payload)
    modes = []
    for item in _capability_records(data, "modes"):
        modes.append(
            ModeDescriptor(
                id=str(item.get("id") or ""),
                label=str(item.get("label") or ""),
                description=str(item.get("description") or ""),
                icon_key=str(item.get("icon_key") or ""),
                color_token=str(item.get("color_token") or ""),
                command_id=str(item.get("command_id") or ""),
            )
        )
    commands = []
    for item in _capability_records(data, "commands"):
        if item.get("active") is False:
            continue
        commands.append(
            CommandDescriptor(
                id=str(item.get("name") or ""),
                label=str(item.get("usage") or ""),
                group=str(item.get("source_type") or ""),
                dispatch=dict(item.get("dispatch") or {}),
                shortcut=str(item.get("shortcut") or ""),
                availability=dict(item.get("availability") or {}),
                summary=str(item.get("summary") or ""),
                source_type=str(item.get("source_type") or ""),
                source_id=str(item.get("source_id") or ""),
            )
        )
    tools = []
    for item in _capability_records(data, "tools"):
        if item.get("active") is False:
            continue
        tools.append(
            ToolPresentation(
                name=str(item.get("name") or ""),
                label=str(item.get("label") or ""),
                icon_key=str(item.get("icon_key") or ""),
                renderer_key=str(item.get("renderer_key") or ""),
                permission_category=str(item.get("permission_category") or ""),
                metadata=dict(item.get("metadata") or {}),
            )
        )
    workflow_packages = []
    for item in _capability_records(data, "workflowPackages"):
        workflow_packages.append(
            WorkflowPackageDescriptor(
                id=str(item.get("id") or ""),
                label=str(item.get("label") or ""),
                active=bool(item.get("active")),
                state=dict(item.get("state") or {}),
                metadata=dict(item.get("metadata") or {}),
            )
        )
    empty_state = data.get("emptyState")
    if empty_state is None:
        empty_state = {}
    if not isinstance(empty_state, dict):
        raise ValueError("capabilities.emptyState must be a mapping")
    agent_application = data.get("agentApplication")
    if agent_application is not None and not isinstance(agent_application, dict):
        raise ValueError("capabilities.agentApplication must be a mapping")
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
                _agent_application_descriptor(item)
                for item in _capability_records(data, "agentApplications")
            ]
            if descriptor is not None
        ],
        resources=_capability_records(data, "resources"),
        model_profiles=_capability_records(data, "modelProfiles"),
        empty_state=dict(empty_state or {}),
    )


def _shell_records(data: Dict[str, Any], key: str) -> list:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise ValueError("shell.%s must be a list" % key)
    return value


def _protocol_shell_descriptor(payload: Any) -> ShellDescriptor:
    data = _normal_mapping(payload)
    if not data:
        return ShellDescriptor(schema_version=FRONTEND_PROTOCOL_SCHEMA_VERSION)
    return ShellDescriptor(
        schema_version=data.get("schema_version"),
        commands=[
            CommandDescriptor(
                id=str(item.get("id") or ""),
                label=str(item.get("label") or ""),
                group=str(item.get("group") or ""),
                dispatch=dict(item.get("dispatch") or {}),
                shortcut=str(item.get("shortcut") or ""),
                availability=dict(item.get("availability") or {}),
                summary=str(item.get("summary") or ""),
                source_type=str(item.get("source_type") or ""),
                source_id=str(item.get("source_id") or ""),
            )
            for item in _shell_records(data, "commands")
        ],
        surfaces=[
            SurfaceDescriptor(
                id=str(item.get("id") or ""),
                label=str(item.get("label") or ""),
                placement=str(item.get("placement") or ""),
                renderer_key=str(item.get("renderer_key") or ""),
                availability=dict(item.get("availability") or {}),
                metadata=dict(item.get("metadata") or {}),
            )
            for item in _shell_records(data, "surfaces")
        ],
        keybindings=[
            KeybindingDescriptor(
                command_id=str(item.get("command_id") or ""),
                keys=str(item.get("keys") or ""),
                when=dict(item.get("when") or {}),
            )
            for item in _shell_records(data, "keybindings")
        ],
        tool_presentations=[
            ToolPresentation(
                name=str(item.get("name") or ""),
                label=str(item.get("label") or ""),
                icon_key=str(item.get("icon_key") or ""),
                renderer_key=str(item.get("renderer_key") or ""),
                permission_category=str(item.get("permission_category") or ""),
                metadata=dict(item.get("metadata") or {}),
            )
            for item in _shell_records(data, "tool_presentations")
        ],
        timeline_items=[
            TimelineItemDescriptor(
                event_kind=str(item.get("event_kind") or ""),
                renderer_key=str(item.get("renderer_key") or ""),
                priority=item.get("priority", 0),
            )
            for item in _shell_records(data, "timeline_items")
        ],
        interactions=[
            InteractionDescriptor(
                kind=str(item.get("kind") or ""),
                renderer_key=str(item.get("renderer_key") or ""),
            )
            for item in _shell_records(data, "interactions")
        ],
    )


def serialize_app_bootstrap(payload: Any) -> Dict[str, Any]:
    data = _normal_mapping(payload)
    active_workspace = data.get("active_workspace")
    return AppBootstrap(
        schema_version=FRONTEND_PROTOCOL_SCHEMA_VERSION,
        app=dict(data.get("app") or {}),
        workspaces=_normal_list(data.get("workspaces")),
        active_workspace=(dict(active_workspace) if isinstance(active_workspace, dict) else None),
        has_active_workspace=bool(data.get("has_active_workspace")),
        shell=_protocol_shell_descriptor(data.get("shell")),
        settings=dict(data.get("settings") or {}),
        diagnostics=dict(data.get("diagnostics") or {}),
        last_failure=(
            FailureRecord.from_dict(data["last_failure"])
            if isinstance(data.get("last_failure"), dict)
            else None
        ),
        removed=bool(data.get("removed")) if "removed" in data else None,
    ).to_dict()


def serialize_session_bootstrap(payload: Any) -> Dict[str, Any]:
    data = _normal_mapping(payload)
    snapshot_payload = serialize_session_snapshot(data.get("snapshot"))
    session_id = str(snapshot_payload.get("session_id") or data.get("session_id") or "")
    thread = _normal_mapping(data.get("thread"))
    history = _normal_mapping(data.get("history"))
    event_cursor = data.get("event_cursor", 0)
    if isinstance(event_cursor, bool) or not isinstance(event_cursor, int):
        raise ValueError("event_cursor must be an integer")
    return SessionBootstrap(
        schema_version=FRONTEND_PROTOCOL_SCHEMA_VERSION,
        event_cursor=event_cursor,
        thread=ThreadShell(
            id=session_id,
            title=str(thread.get("title") or ""),
            archived=bool(thread.get("archived")),
            current_mode=str(snapshot_payload.get("current_mode") or ""),
            status=str(snapshot_payload.get("status") or ""),
            updated_at=str(snapshot_payload.get("updated_at") or ""),
            pending_interaction=bool(snapshot_payload.get("pending_interaction_valid")),
        ),
        snapshot=snapshot_payload,
        activities=_normal_list(history.get("activities")),
        capabilities=_protocol_capability_snapshot(data.get("capabilities")),
        integrity=dict(history.get("integrity") or {}),
        plan=serialize_plan_snapshot(data.get("plan")),
        permission_context=serialize_permission_context(data.get("permission_context")),
    ).to_dict()


def serialize_session_snapshot(snapshot: Any) -> Dict[str, Any]:
    pending_interaction = to_mapping(read_value(snapshot, "pending_interaction"))
    runtime_environment = to_mapping(read_value(snapshot, "runtime_environment"))
    pending_interaction_valid = read_value(snapshot, "pending_interaction_valid", None)
    if pending_interaction_valid is None:
        pending_interaction_valid = bool(pending_interaction)
    return {
        "session_id": str(read_value(snapshot, "session_id", "") or ""),
        "status": read_status_value(snapshot),
        "current_mode": str(read_value(snapshot, "current_mode", "") or ""),
        "started_at": str(read_value(snapshot, "started_at", "", aliases=("created_at",)) or ""),
        "updated_at": str(read_value(snapshot, "updated_at", "") or ""),
        "workflow_state": dict(read_value(snapshot, "workflow_state", {}) or {}),
        "has_active_plan": bool(read_value(snapshot, "has_active_plan", False)),
        "active_plan_ref": str(read_value(snapshot, "active_plan_ref", "") or ""),
        "current_command_context": str(read_value(snapshot, "current_command_context", "") or ""),
        "pending_interaction": pending_interaction,
        "last_failure": dict(read_value(snapshot, "last_failure", {}) or {}) or None,
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
    return _protocol_capability_snapshot(payload).to_dict()
