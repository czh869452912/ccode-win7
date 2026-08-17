from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

from .errors import CompositionError


_ENTRY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$")
_RUNTIME_REQUIREMENT_RE = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$")


@dataclass(frozen=True)
class DistributionManifest(object):
    distribution_id: str
    version: str
    import_root: str
    runtime_only: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "distribution_id": str(self.distribution_id),
            "version": str(self.version),
            "import_root": str(self.import_root),
            "runtime_only": bool(self.runtime_only),
        }


@dataclass(frozen=True)
class ApplicationManifest(object):
    application_id: str
    version: str
    api_version: str
    distribution_id: str
    registration_entry: str
    requires: Tuple[str, ...] = field(default_factory=tuple)
    conflicts: Tuple[str, ...] = field(default_factory=tuple)
    capabilities: Tuple[str, ...] = field(default_factory=tuple)
    permission_categories: Tuple[str, ...] = field(default_factory=tuple)
    prompt_resources: Tuple[str, ...] = field(default_factory=tuple)
    toolset_ids: Tuple[str, ...] = field(default_factory=tuple)
    context_provider_ids: Tuple[str, ...] = field(default_factory=tuple)
    workflow_state_namespace: str = ""
    shell_contribution_ids: Tuple[str, ...] = field(default_factory=tuple)
    runtime_requirements: Tuple[str, ...] = field(default_factory=tuple)
    asset_ids: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        validate_application_manifest(self)
        return {
            "application_id": str(self.application_id),
            "version": str(self.version),
            "api_version": str(self.api_version),
            "distribution_id": str(self.distribution_id),
            "registration_entry": str(self.registration_entry),
            "requires": list(self.requires),
            "conflicts": list(self.conflicts),
            "capabilities": list(self.capabilities),
            "permission_categories": list(self.permission_categories),
            "prompt_resources": list(self.prompt_resources),
            "toolset_ids": list(self.toolset_ids),
            "context_provider_ids": list(self.context_provider_ids),
            "workflow_state_namespace": str(self.workflow_state_namespace or ""),
            "shell_contribution_ids": list(self.shell_contribution_ids),
            "runtime_requirements": list(self.runtime_requirements),
            "asset_ids": list(self.asset_ids),
        }


def _require_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CompositionError("invalid_application_manifest", field_name)
    return text


def _require_unique_texts(values: Tuple[str, ...], field_name: str) -> None:
    normalized = tuple(str(value or "").strip() for value in values)
    if any(not value for value in normalized) or len(set(normalized)) != len(normalized):
        raise CompositionError("invalid_application_manifest", field_name)


def validate_application_manifest(manifest: ApplicationManifest) -> ApplicationManifest:
    if not isinstance(manifest, ApplicationManifest):
        raise CompositionError("invalid_application_manifest", "expected ApplicationManifest")
    for field_name in ("application_id", "version", "api_version", "distribution_id"):
        _require_text(getattr(manifest, field_name), field_name)
    registration_entry = _require_text(manifest.registration_entry, "registration_entry")
    if _ENTRY_RE.fullmatch(registration_entry) is None:
        raise CompositionError("invalid_application_manifest", "registration_entry")
    for field_name in (
        "requires",
        "conflicts",
        "capabilities",
        "permission_categories",
        "prompt_resources",
        "toolset_ids",
        "context_provider_ids",
        "shell_contribution_ids",
        "runtime_requirements",
        "asset_ids",
    ):
        values = tuple(getattr(manifest, field_name) or ())
        _require_unique_texts(values, field_name)
        if field_name == "runtime_requirements":
            for requirement in values:
                if _RUNTIME_REQUIREMENT_RE.fullmatch(requirement) is None:
                    raise CompositionError("invalid_application_manifest", requirement)
    if manifest.workflow_state_namespace:
        _require_text(manifest.workflow_state_namespace, "workflow_state_namespace")
    return manifest
