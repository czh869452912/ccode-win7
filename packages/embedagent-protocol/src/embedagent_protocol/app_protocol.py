from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

from embedagent_protocol.session_events import FailureRecord
from embedagent_protocol.versions import FRONTEND_PROTOCOL_SCHEMA_VERSION

SURFACE_PLACEMENTS = ("overlay", "secondary")


def _require_schema_version(value: Any, field_name: str = "schema_version") -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value != FRONTEND_PROTOCOL_SCHEMA_VERSION
    ):
        raise ValueError("%s must be %s" % (field_name, FRONTEND_PROTOCOL_SCHEMA_VERSION))
    return value


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("%s must be non-blank" % field_name)
    return value


def _copy_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _copy_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy_value(item) for item in value]
    return value


def _require_mapping(value: Any, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("%s must be a mapping" % field_name)
    return _copy_value(value)


def _require_list(value: Any, field_name: str) -> List[Any]:
    if not isinstance(value, list):
        raise ValueError("%s must be a list" % field_name)
    return value


def _require_items(value: Any, item_type: Type[Any], field_name: str) -> List[Any]:
    items = _require_list(value, field_name)
    if any(not isinstance(item, item_type) for item in items):
        raise ValueError("%s contains an invalid item" % field_name)
    return items


def _unique_ids(kind: str, records: List[Any]) -> set:
    record_ids = set()
    for record in records:
        record_id = record.id
        if record_id in record_ids:
            raise ValueError("duplicate_%s:%s" % (kind, record_id))
        record_ids.add(record_id)
    return record_ids


def _serialize_activity(value: Any) -> Dict[str, Any]:
    if hasattr(value, "to_dict"):
        payload = value.to_dict()
        return _require_mapping(payload, "activity")
    return _require_mapping(value, "activity")


@dataclass
class ModeDescriptor:
    id: str
    label: str
    description: str = ""
    icon_key: str = ""
    color_token: str = ""
    command_id: str = ""

    def __post_init__(self) -> None:
        _require_text(self.id, "mode.id")
        _require_text(self.label, "mode.label")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "icon_key": self.icon_key,
            "color_token": self.color_token,
            "command_id": self.command_id,
        }


@dataclass
class CommandDescriptor:
    id: str
    label: str
    group: str
    dispatch: Dict[str, Any] = field(default_factory=dict)
    shortcut: str = ""
    availability: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    source_type: str = ""
    source_id: str = ""

    def __post_init__(self) -> None:
        _require_text(self.id, "command.id")
        _require_text(self.label, "command.label")
        _require_text(self.group, "command.group")
        _require_mapping(self.dispatch, "command.dispatch")
        _require_mapping(self.availability, "command.availability")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "group": self.group,
            "dispatch": _require_mapping(self.dispatch, "command.dispatch"),
            "shortcut": self.shortcut,
            "availability": _require_mapping(self.availability, "command.availability"),
            "summary": self.summary,
            "source_type": self.source_type,
            "source_id": self.source_id,
        }


@dataclass
class SurfaceDescriptor:
    id: str
    label: str
    placement: str
    renderer_key: str
    availability: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.id, "surface.id")
        _require_text(self.label, "surface.label")
        if self.placement not in SURFACE_PLACEMENTS:
            raise ValueError("surface.placement is invalid")
        _require_text(self.renderer_key, "surface.renderer_key")
        _require_mapping(self.availability, "surface.availability")
        _require_mapping(self.metadata, "surface.metadata")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "placement": self.placement,
            "renderer_key": self.renderer_key,
            "availability": _require_mapping(self.availability, "surface.availability"),
            "metadata": _require_mapping(self.metadata, "surface.metadata"),
        }


@dataclass
class KeybindingDescriptor:
    command_id: str
    keys: str
    when: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.command_id, "keybinding.command_id")
        _require_text(self.keys, "keybinding.keys")
        _require_mapping(self.when, "keybinding.when")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "keys": self.keys,
            "when": _require_mapping(self.when, "keybinding.when"),
        }


@dataclass
class ToolPresentation:
    name: str
    label: str
    icon_key: str = ""
    renderer_key: str = "generic"
    permission_category: str = "other"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.name, "tool_presentation.name")
        _require_text(self.label, "tool_presentation.label")
        _require_text(self.renderer_key, "tool_presentation.renderer_key")
        _require_text(self.permission_category, "tool_presentation.permission_category")
        _require_mapping(self.metadata, "tool_presentation.metadata")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "icon_key": self.icon_key,
            "renderer_key": self.renderer_key,
            "permission_category": self.permission_category,
            "metadata": _require_mapping(self.metadata, "tool_presentation.metadata"),
        }


@dataclass
class TimelineItemDescriptor:
    event_kind: str
    renderer_key: str
    priority: int = 0

    def __post_init__(self) -> None:
        _require_text(self.event_kind, "timeline_item.event_kind")
        _require_text(self.renderer_key, "timeline_item.renderer_key")
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise ValueError("timeline_item.priority must be an integer")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_kind": self.event_kind,
            "renderer_key": self.renderer_key,
            "priority": self.priority,
        }


@dataclass
class InteractionDescriptor:
    kind: str
    renderer_key: str

    def __post_init__(self) -> None:
        _require_text(self.kind, "interaction.kind")
        _require_text(self.renderer_key, "interaction.renderer_key")

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "renderer_key": self.renderer_key}


@dataclass
class WorkflowPackageDescriptor:
    id: str
    label: str
    active: bool = False
    state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.id, "workflow_package.id")
        _require_text(self.label, "workflow_package.label")
        _require_mapping(self.state, "workflow_package.state")
        _require_mapping(self.metadata, "workflow_package.metadata")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "active": bool(self.active),
            "state": _require_mapping(self.state, "workflow_package.state"),
            "metadata": _require_mapping(self.metadata, "workflow_package.metadata"),
        }


@dataclass
class AgentApplicationDescriptor:
    id: str
    label: str
    profile_id: str = ""
    workflow_package_ids: List[str] = field(default_factory=list)
    active: bool = False
    source_type: str = ""
    source_id: str = ""
    default: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.id, "agent_application.id")
        _require_text(self.label, "agent_application.label")
        _require_list(self.workflow_package_ids, "agent_application.workflow_package_ids")
        if any(not isinstance(item, str) or not item.strip() for item in self.workflow_package_ids):
            raise ValueError("agent_application.workflow_package_ids contains a blank id")
        _require_mapping(self.metadata, "agent_application.metadata")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "profile_id": self.profile_id,
            "workflow_package_ids": list(self.workflow_package_ids),
            "active": bool(self.active),
            "source_type": self.source_type,
            "source_id": self.source_id,
            "default": bool(self.default),
            "metadata": _require_mapping(self.metadata, "agent_application.metadata"),
        }


@dataclass
class CapabilitySnapshot:
    schema_version: int = FRONTEND_PROTOCOL_SCHEMA_VERSION
    modes: List[ModeDescriptor] = field(default_factory=list)
    commands: List[CommandDescriptor] = field(default_factory=list)
    tools: List[ToolPresentation] = field(default_factory=list)
    workflow_packages: List[WorkflowPackageDescriptor] = field(default_factory=list)
    agent_application: Optional[AgentApplicationDescriptor] = None
    agent_applications: List[AgentApplicationDescriptor] = field(default_factory=list)
    resources: List[Dict[str, Any]] = field(default_factory=list)
    model_profiles: List[Dict[str, Any]] = field(default_factory=list)
    empty_state: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version)
        _require_items(self.modes, ModeDescriptor, "capabilities.modes")
        _require_items(self.commands, CommandDescriptor, "capabilities.commands")
        _require_items(self.tools, ToolPresentation, "capabilities.tools")
        _require_items(
            self.workflow_packages,
            WorkflowPackageDescriptor,
            "capabilities.workflow_packages",
        )
        if self.agent_application is not None and not isinstance(
            self.agent_application, AgentApplicationDescriptor
        ):
            raise ValueError("capabilities.agent_application is invalid")
        _require_items(
            self.agent_applications,
            AgentApplicationDescriptor,
            "capabilities.agent_applications",
        )
        for field_name, records in (
            ("capabilities.resources", self.resources),
            ("capabilities.model_profiles", self.model_profiles),
        ):
            _require_list(records, field_name)
            for record in records:
                _require_mapping(record, field_name)
        _require_mapping(self.empty_state, "capabilities.empty_state")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "modes": [item.to_dict() for item in self.modes],
            "commands": [item.to_dict() for item in self.commands],
            "tools": [item.to_dict() for item in self.tools],
            "workflow_packages": [item.to_dict() for item in self.workflow_packages],
            "agent_application": (
                self.agent_application.to_dict() if self.agent_application is not None else {}
            ),
            "agent_applications": [item.to_dict() for item in self.agent_applications],
            "resources": [
                _require_mapping(item, "capabilities.resources") for item in self.resources
            ],
            "model_profiles": [
                _require_mapping(item, "capabilities.model_profiles")
                for item in self.model_profiles
            ],
            "empty_state": _require_mapping(self.empty_state, "capabilities.empty_state"),
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "CapabilitySnapshot":
        payload = _require_mapping(value, "capabilities")
        agent_application = payload.get("agent_application")
        return cls(
            schema_version=payload.get("schema_version"),
            modes=[
                ModeDescriptor(**_require_mapping(item, "mode"))
                for item in payload.get("modes", [])
            ],
            commands=[
                CommandDescriptor(**_require_mapping(item, "command"))
                for item in payload.get("commands", [])
            ],
            tools=[
                ToolPresentation(**_require_mapping(item, "tool_presentation"))
                for item in payload.get("tools", [])
            ],
            workflow_packages=[
                WorkflowPackageDescriptor(**_require_mapping(item, "workflow_package"))
                for item in payload.get("workflow_packages", [])
            ],
            agent_application=(
                AgentApplicationDescriptor(
                    **_require_mapping(agent_application, "agent_application")
                )
                if isinstance(agent_application, dict) and agent_application
                else None
            ),
            agent_applications=[
                AgentApplicationDescriptor(**_require_mapping(item, "agent_application"))
                for item in payload.get("agent_applications", [])
            ],
            resources=_require_list(payload.get("resources", []), "capabilities.resources"),
            model_profiles=_require_list(
                payload.get("model_profiles", []),
                "capabilities.model_profiles",
            ),
            empty_state=_require_mapping(
                payload.get("empty_state", {}),
                "capabilities.empty_state",
            ),
        )


@dataclass
class ShellDescriptor:
    schema_version: int = FRONTEND_PROTOCOL_SCHEMA_VERSION
    commands: List[CommandDescriptor] = field(default_factory=list)
    surfaces: List[SurfaceDescriptor] = field(default_factory=list)
    keybindings: List[KeybindingDescriptor] = field(default_factory=list)
    tool_presentations: List[ToolPresentation] = field(default_factory=list)
    timeline_items: List[TimelineItemDescriptor] = field(default_factory=list)
    interactions: List[InteractionDescriptor] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version)
        for records, item_type, field_name in (
            (self.commands, CommandDescriptor, "shell.commands"),
            (self.surfaces, SurfaceDescriptor, "shell.surfaces"),
            (self.keybindings, KeybindingDescriptor, "shell.keybindings"),
            (self.tool_presentations, ToolPresentation, "shell.tool_presentations"),
            (self.timeline_items, TimelineItemDescriptor, "shell.timeline_items"),
            (self.interactions, InteractionDescriptor, "shell.interactions"),
        ):
            _require_items(records, item_type, field_name)
        command_ids = _unique_ids("shell_command", self.commands)
        _unique_ids("shell_surface", self.surfaces)
        for command in self.commands:
            dispatch_kind = command.dispatch.get("kind")
            if not isinstance(dispatch_kind, str) or not dispatch_kind.strip():
                raise ValueError("shell_command_dispatch_kind:%s" % command.id)
        for keybinding in self.keybindings:
            if keybinding.command_id not in command_ids:
                raise ValueError("unknown_keybinding_command:%s" % keybinding.command_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "commands": [item.to_dict() for item in self.commands],
            "surfaces": [item.to_dict() for item in self.surfaces],
            "keybindings": [item.to_dict() for item in self.keybindings],
            "tool_presentations": [item.to_dict() for item in self.tool_presentations],
            "timeline_items": [item.to_dict() for item in self.timeline_items],
            "interactions": [item.to_dict() for item in self.interactions],
        }


@dataclass
class ThreadShell:
    id: str
    title: str
    archived: bool
    current_mode: str
    status: str
    updated_at: str
    pending_interaction: bool = False

    def __post_init__(self) -> None:
        _require_text(self.id, "thread.id")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "archived": bool(self.archived),
            "current_mode": self.current_mode,
            "status": self.status,
            "updated_at": self.updated_at,
            "pending_interaction": bool(self.pending_interaction),
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ThreadShell":
        payload = _require_mapping(value, "thread")
        return cls(
            id=payload.get("id"),
            title=payload.get("title", ""),
            archived=payload.get("archived", False),
            current_mode=payload.get("current_mode", ""),
            status=payload.get("status", ""),
            updated_at=payload.get("updated_at", ""),
            pending_interaction=payload.get("pending_interaction", False),
        )


@dataclass
class InteractionActivity:
    id: str
    kind: str
    request_id: str
    turn_id: str
    created_at: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.id, "activity.id")
        _require_text(self.kind, "activity.kind")
        _require_text(self.request_id, "activity.request_id")
        _require_mapping(self.payload, "activity.payload")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "request_id": self.request_id,
            "turn_id": self.turn_id,
            "created_at": self.created_at,
            "payload": _require_mapping(self.payload, "activity.payload"),
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "InteractionActivity":
        payload = _require_mapping(value, "activity")
        return cls(
            id=payload.get("id"),
            kind=payload.get("kind"),
            request_id=payload.get("request_id"),
            turn_id=payload.get("turn_id", ""),
            created_at=payload.get("created_at", ""),
            payload=_require_mapping(payload.get("payload", {}), "activity.payload"),
        )


@dataclass
class SessionBootstrap:
    schema_version: int
    event_cursor: int
    thread: ThreadShell
    snapshot: Dict[str, Any]
    activities: List[Any]
    capabilities: CapabilitySnapshot
    integrity: Dict[str, Any] = field(default_factory=dict)
    plan: Optional[Dict[str, Any]] = None
    permission_context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version)
        if isinstance(self.event_cursor, bool) or not isinstance(self.event_cursor, int):
            raise ValueError("event_cursor must be an integer")
        if self.event_cursor < 0:
            raise ValueError("event_cursor must be non-negative")
        if not isinstance(self.thread, ThreadShell):
            raise ValueError("thread must be a ThreadShell")
        _require_mapping(self.snapshot, "snapshot")
        _require_list(self.activities, "activities")
        if not isinstance(self.capabilities, CapabilitySnapshot):
            raise ValueError("capabilities must be a CapabilitySnapshot")
        _require_mapping(self.integrity, "integrity")
        if self.plan is not None:
            _require_mapping(self.plan, "plan")
        _require_mapping(self.permission_context, "permission_context")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_cursor": self.event_cursor,
            "thread": self.thread.to_dict(),
            "snapshot": _require_mapping(self.snapshot, "snapshot"),
            "history": {
                "activities": [_serialize_activity(item) for item in self.activities],
                "integrity": _require_mapping(self.integrity, "integrity"),
            },
            "capabilities": self.capabilities.to_dict(),
            "plan": _require_mapping(self.plan, "plan") if self.plan is not None else None,
            "permission_context": _require_mapping(
                self.permission_context,
                "permission_context",
            ),
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "SessionBootstrap":
        payload = _require_mapping(value, "session_bootstrap")
        history = _require_mapping(payload.get("history", {}), "history")
        activities = _require_list(history.get("activities", []), "history.activities")
        restored_activities = []
        for item in activities:
            activity = _require_mapping(item, "activity")
            if activity.get("request_id"):
                restored_activities.append(InteractionActivity.from_dict(activity))
            else:
                restored_activities.append(activity)
        return cls(
            schema_version=payload.get("schema_version"),
            event_cursor=payload.get("event_cursor"),
            thread=ThreadShell.from_dict(payload.get("thread")),
            snapshot=_require_mapping(payload.get("snapshot"), "snapshot"),
            activities=restored_activities,
            capabilities=CapabilitySnapshot.from_dict(payload.get("capabilities")),
            integrity=_require_mapping(history.get("integrity", {}), "history.integrity"),
            plan=(
                _require_mapping(payload.get("plan"), "plan")
                if payload.get("plan") is not None
                else None
            ),
            permission_context=_require_mapping(
                payload.get("permission_context", {}),
                "permission_context",
            ),
        )


@dataclass
class AppBootstrap:
    schema_version: int
    app: Dict[str, Any]
    workspaces: List[Dict[str, Any]]
    shell: ShellDescriptor
    active_workspace: Optional[Dict[str, Any]] = None
    has_active_workspace: bool = False
    settings: Dict[str, Any] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    last_failure: Optional[FailureRecord] = None
    removed: Optional[bool] = None

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version)
        _require_mapping(self.app, "app")
        _require_list(self.workspaces, "workspaces")
        for workspace in self.workspaces:
            _require_mapping(workspace, "workspaces")
        if not isinstance(self.shell, ShellDescriptor):
            raise ValueError("shell must be a ShellDescriptor")
        if self.active_workspace is not None:
            _require_mapping(self.active_workspace, "active_workspace")
        _require_mapping(self.settings, "settings")
        _require_mapping(self.diagnostics, "diagnostics")
        if self.last_failure is not None and not isinstance(self.last_failure, FailureRecord):
            raise ValueError("last_failure must be a FailureRecord")
        if self.removed is not None and not isinstance(self.removed, bool):
            raise ValueError("removed must be a bool")

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "app": _require_mapping(self.app, "app"),
            "workspaces": [_require_mapping(item, "workspaces") for item in self.workspaces],
            "active_workspace": (
                _require_mapping(self.active_workspace, "active_workspace")
                if self.active_workspace is not None
                else None
            ),
            "has_active_workspace": bool(self.has_active_workspace),
            "shell": self.shell.to_dict(),
            "settings": _require_mapping(self.settings, "settings"),
            "diagnostics": _require_mapping(self.diagnostics, "diagnostics"),
            "last_failure": (
                self.last_failure.to_dict() if self.last_failure is not None else None
            ),
        }
        if self.removed is not None:
            payload["removed"] = self.removed
        return payload
