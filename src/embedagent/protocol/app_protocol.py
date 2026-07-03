from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


@dataclass
class ModeDescriptor:
    id: str
    label: str
    description: str = ""
    icon_key: str = ""
    color_token: str = ""
    command_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "iconKey": self.icon_key,
            "colorToken": self.color_token,
            "commandId": self.command_id,
        }


@dataclass
class CommandDescriptor:
    id: str
    label: str
    group: str
    dispatch: Dict[str, Any] = field(default_factory=dict)
    shortcut: str = ""
    availability: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "group": self.group,
            "dispatch": _dict(self.dispatch),
            "shortcut": self.shortcut,
            "availability": _dict(self.availability),
        }


@dataclass
class ToolPresentation:
    name: str
    label: str
    icon_key: str = ""
    renderer_key: str = "generic"
    permission_category: str = "other"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "iconKey": self.icon_key,
            "rendererKey": self.renderer_key,
            "permissionCategory": self.permission_category,
            "metadata": _dict(self.metadata),
        }


@dataclass
class WorkflowPackageDescriptor:
    id: str
    label: str
    active: bool = False
    state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "active": bool(self.active),
            "state": _dict(self.state),
            "metadata": _dict(self.metadata),
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "applicationId": self.id,
            "label": self.label,
            "profileId": self.profile_id,
            "workflowPackageIds": [str(item) for item in self.workflow_package_ids],
            "active": bool(self.active),
            "sourceType": self.source_type,
            "sourceId": self.source_id,
            "default": bool(self.default),
            "metadata": _dict(self.metadata),
        }


@dataclass
class CapabilitySnapshot:
    version: int = 1
    modes: List[ModeDescriptor] = field(default_factory=list)
    commands: List[CommandDescriptor] = field(default_factory=list)
    tools: List[ToolPresentation] = field(default_factory=list)
    workflow_packages: List[WorkflowPackageDescriptor] = field(default_factory=list)
    agent_application: Optional[AgentApplicationDescriptor] = None
    agent_applications: List[AgentApplicationDescriptor] = field(default_factory=list)
    resources: List[Dict[str, Any]] = field(default_factory=list)
    model_profiles: List[Dict[str, Any]] = field(default_factory=list)
    empty_state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": int(self.version),
            "modes": [item.to_dict() for item in self.modes],
            "commands": [item.to_dict() for item in self.commands],
            "tools": [item.to_dict() for item in self.tools],
            "workflowPackages": [item.to_dict() for item in self.workflow_packages],
            "agentApplication": (
                self.agent_application.to_dict() if self.agent_application is not None else {}
            ),
            "agentApplications": [item.to_dict() for item in self.agent_applications],
            "resources": [_dict(item) for item in self.resources],
            "modelProfiles": [_dict(item) for item in self.model_profiles],
            "emptyState": _dict(self.empty_state),
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "archived": bool(self.archived),
            "currentMode": self.current_mode,
            "status": self.status,
            "updatedAt": self.updated_at,
            "pendingInteraction": bool(self.pending_interaction),
        }


@dataclass
class InteractionActivity:
    id: str
    kind: str
    request_id: str
    turn_id: str
    created_at: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "requestId": self.request_id,
            "turnId": self.turn_id,
            "createdAt": self.created_at,
            "payload": _dict(self.payload),
        }


@dataclass
class ThreadDetailSnapshot:
    thread: ThreadShell
    snapshot: Dict[str, Any]
    activities: List[Any]
    capabilities: CapabilitySnapshot
    workflow: Dict[str, Any] = field(default_factory=dict)
    integrity: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        activity_payloads = []
        for item in self.activities:
            activity_payloads.append(item.to_dict() if hasattr(item, "to_dict") else _dict(item))
        return {
            "thread": self.thread.to_dict(),
            "snapshot": _dict(self.snapshot),
            "history": {
                "activities": activity_payloads,
                "integrity": _dict(self.integrity),
            },
            "capabilities": self.capabilities.to_dict(),
            "workflow": _dict(self.workflow),
        }


@dataclass
class AppBootstrap:
    app: Dict[str, Any]
    workspaces: List[Dict[str, Any]]
    commands: List[CommandDescriptor]
    surfaces: List[Dict[str, Any]]
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app": _dict(self.app),
            "workspaces": [_dict(item) for item in self.workspaces],
            "commands": [item.to_dict() for item in self.commands],
            "surfaces": [_dict(item) for item in self.surfaces],
            "diagnostics": _dict(self.diagnostics),
        }
