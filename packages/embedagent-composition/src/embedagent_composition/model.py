from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class ComponentRef:
    component_id: str
    version: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "component_id": str(self.component_id),
            "version": str(self.version or ""),
        }


@dataclass(frozen=True)
class ComponentManifest:
    component_id: str
    kind: str
    version: str
    api_version: str
    requires: Tuple[str, ...] = field(default_factory=tuple)
    conflicts: Tuple[str, ...] = field(default_factory=tuple)
    permission_categories: Tuple[str, ...] = field(default_factory=tuple)
    runtime_assets: Tuple[str, ...] = field(default_factory=tuple)
    resource_scopes: Tuple[str, ...] = field(default_factory=tuple)
    namespaces: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": str(self.component_id),
            "kind": str(self.kind),
            "version": str(self.version),
            "api_version": str(self.api_version),
            "requires": list(self.requires),
            "conflicts": list(self.conflicts),
            "permission_categories": list(self.permission_categories),
            "runtime_assets": list(self.runtime_assets),
            "resource_scopes": list(self.resource_scopes),
            "namespaces": list(self.namespaces),
        }


@dataclass(frozen=True)
class AgentProductDefinition:
    agent_id: str
    profile: ComponentRef
    providers: Tuple[ComponentRef, ...] = field(default_factory=tuple)
    workflows: Tuple[ComponentRef, ...] = field(default_factory=tuple)
    tools: Tuple[ComponentRef, ...] = field(default_factory=tuple)
    resources: Tuple[ComponentRef, ...] = field(default_factory=tuple)
    host: Optional[ComponentRef] = None
    gui: Optional[ComponentRef] = None

    def component_refs(self) -> Tuple[ComponentRef, ...]:
        refs = [self.profile]
        refs.extend(self.providers)
        refs.extend(self.workflows)
        refs.extend(self.tools)
        refs.extend(self.resources)
        if self.host is not None:
            refs.append(self.host)
        if self.gui is not None:
            refs.append(self.gui)
        return tuple(refs)


@dataclass(frozen=True)
class CompiledAgentSpec:
    agent_id: str
    manifest: Dict[str, Any]
    lock: Dict[str, Any]
    files: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "manifest": self.manifest,
            "lock": self.lock,
            "files": list(self.files),
        }
