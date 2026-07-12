from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class WorkflowPackageManifestError(ValueError):
    pass


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _stable_list(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []
    result = []
    seen = set()
    for item in items:
        text = _clean_text(item)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return sorted(result)


def _stable_ordered_list(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []
    result = []
    seen = set()
    for item in items:
        text = _clean_text(item)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _copy_dict(value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


@dataclass
class WorkflowToolDeclaration(object):
    name: str
    permission_category: str = "other"
    source_type: str = "workflow_package"
    source_id: str = "workflow_package"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.name = _clean_text(self.name)
        self.permission_category = _clean_text(self.permission_category) or "other"
        self.source_type = _clean_text(self.source_type) or "workflow_package"
        self.source_id = _clean_text(self.source_id) or self.source_type
        self.metadata = _copy_dict(self.metadata)
        if not self.name:
            raise WorkflowPackageManifestError("workflow tool declaration requires name")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "permission_category": self.permission_category,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "metadata": _copy_dict(self.metadata),
        }


@dataclass
class WorkflowPackDeclaration(object):
    name: str
    tool_names: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = _clean_text(self.name)
        self.tool_names = _stable_ordered_list(self.tool_names)
        if not self.name:
            raise WorkflowPackageManifestError("workflow pack declaration requires name")

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "tool_names": list(self.tool_names)}


@dataclass
class WorkflowPackageManifest(object):
    package_id: str
    label: str
    version: str = "1"
    source_type: str = "builtin"
    source_id: str = "workflow_package"
    supported_modes: List[str] = field(default_factory=list)
    supported_workflow_states: List[str] = field(default_factory=list)
    tools: List[WorkflowToolDeclaration] = field(default_factory=list)
    packs: List[WorkflowPackDeclaration] = field(default_factory=list)
    resource_scopes: List[str] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.package_id = _clean_text(self.package_id)
        self.label = _clean_text(self.label)
        self.version = _clean_text(self.version) or "1"
        self.source_type = _clean_text(self.source_type) or "builtin"
        self.source_id = _clean_text(self.source_id) or self.package_id
        self.supported_modes = _stable_list(self.supported_modes)
        self.supported_workflow_states = _stable_list(self.supported_workflow_states)
        self.tools = list(self.tools or [])
        self.packs = list(self.packs or [])
        self.resource_scopes = _stable_list(self.resource_scopes)
        self.diagnostics = [
            dict(item) for item in list(self.diagnostics or []) if isinstance(item, dict)
        ]
        if not self.package_id:
            raise WorkflowPackageManifestError("workflow package manifest requires package_id")
        if not self.label:
            raise WorkflowPackageManifestError("workflow package manifest requires label")

    def to_dict(self) -> Dict[str, Any]:
        tools = sorted([item.to_dict() for item in self.tools], key=lambda item: item["name"])
        packs = sorted([item.to_dict() for item in self.packs], key=lambda item: item["name"])
        return {
            "package_id": self.package_id,
            "label": self.label,
            "version": self.version,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "supported_modes": list(self.supported_modes),
            "supported_workflow_states": list(self.supported_workflow_states),
            "tools": tools,
            "packs": packs,
            "resource_scopes": list(self.resource_scopes),
            "diagnostics": [dict(item) for item in self.diagnostics],
        }
