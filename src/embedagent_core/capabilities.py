from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

CAPABILITY_KINDS = ("command", "mode", "model_profile", "resource", "tool", "workflow_package")


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    return deepcopy(metadata)


@dataclass
class CapabilityDescriptor:
    name: str
    kind: str
    source_type: str = "runtime"
    source_id: str = "runtime"
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)
    active: bool = False

    def __post_init__(self) -> None:
        self.name = _clean_text(self.name)
        self.kind = _clean_text(self.kind)
        self.source_type = _clean_text(self.source_type, "runtime")
        self.source_id = _clean_text(self.source_id, self.source_type)
        self.metadata = _safe_metadata(self.metadata)
        self.active = bool(self.active)
        if not self.name:
            raise ValueError("capability descriptor name is required")
        if not self.kind:
            raise ValueError("capability descriptor kind is required")

    def key(self) -> Tuple[str, str, str, str]:
        return (self.kind, self.name, self.source_type, self.source_id)

    def copy(self) -> "CapabilityDescriptor":
        return CapabilityDescriptor(
            name=self.name,
            kind=self.kind,
            source_type=self.source_type,
            source_id=self.source_id,
            metadata=deepcopy(self.metadata or {}),
            active=self.active,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "metadata": deepcopy(self.metadata or {}),
            "active": bool(self.active),
        }


@dataclass
class CapabilitySnapshot:
    descriptors: List[CapabilityDescriptor]

    def descriptors_for_kind(self, kind: str) -> List[CapabilityDescriptor]:
        normalized = _clean_text(kind)
        return [item.copy() for item in self.descriptors if item.kind == normalized]

    def counts(self) -> Dict[str, int]:
        payload = dict((kind, 0) for kind in CAPABILITY_KINDS)
        for item in self.descriptors:
            payload[item.kind] = int(payload.get(item.kind, 0)) + 1
        return payload

    def active_names_by_kind(self) -> Dict[str, List[str]]:
        payload = dict((kind, []) for kind in CAPABILITY_KINDS)
        for item in self.descriptors:
            if item.active:
                payload.setdefault(item.kind, []).append(item.name)
        for names in payload.values():
            names.sort()
        return payload

    def to_dict(self) -> Dict[str, Any]:
        ordered = sorted(
            [item.copy() for item in self.descriptors],
            key=lambda item: item.key(),
        )
        return {
            "descriptors": [item.to_dict() for item in ordered],
            "counts": self.counts(),
            "active_names_by_kind": self.active_names_by_kind(),
        }


class CapabilityRegistry(object):
    def __init__(self, descriptors: Optional[Iterable[CapabilityDescriptor]] = None) -> None:
        self._descriptors = {}  # type: Dict[Tuple[str, str, str, str], CapabilityDescriptor]
        for descriptor in list(descriptors or []):
            self.register(descriptor)

    def register(self, descriptor: CapabilityDescriptor) -> None:
        if not isinstance(descriptor, CapabilityDescriptor):
            raise ValueError("capability descriptor is required")
        self._descriptors[descriptor.key()] = descriptor.copy()

    def extend(self, descriptors: Iterable[CapabilityDescriptor]) -> None:
        for descriptor in list(descriptors or []):
            self.register(descriptor)

    def descriptors(self, kind: Optional[str] = None) -> List[CapabilityDescriptor]:
        normalized_kind = _clean_text(kind) if kind is not None else ""
        items = [item.copy() for item in self._descriptors.values()]
        if normalized_kind:
            items = [item for item in items if item.kind == normalized_kind]
        return sorted(items, key=lambda item: item.key())

    def snapshot(self) -> CapabilitySnapshot:
        return CapabilitySnapshot(self.descriptors())


def runtime_tool_capability_descriptors(runtime: Any) -> List[CapabilityDescriptor]:
    catalog = []
    catalog_method = getattr(runtime, "catalog_entries", None)
    if callable(catalog_method):
        catalog = list(catalog_method() or [])
    descriptors = []
    for entry in catalog:
        if not isinstance(entry, dict):
            continue
        name = _clean_text(entry.get("name"))
        if not name:
            continue
        descriptors.append(
            CapabilityDescriptor(
                name=name,
                kind="tool",
                source_type=_clean_text(entry.get("source_type"), "runtime"),
                source_id=_clean_text(entry.get("source_id"), "runtime"),
                metadata=dict(entry),
                active=False,
            )
        )
    return descriptors


def resource_capability_descriptors(resources: Dict[str, Any]) -> List[CapabilityDescriptor]:
    descriptors = []
    if not isinstance(resources, dict):
        return descriptors
    resource_groups = (
        ("skills", "skill", "path"),
        ("prompts", "prompt", "path"),
        ("recipes", "recipe", "id"),
    )
    for group_name, source_id, name_key in resource_groups:
        for item in list(resources.get(group_name) or []):
            if not isinstance(item, dict):
                continue
            name = _clean_text(item.get(name_key))
            if not name:
                continue
            metadata = dict(item)
            metadata["resource_group"] = group_name
            descriptors.append(
                CapabilityDescriptor(
                    name=name,
                    kind="resource",
                    source_type=_clean_text(item.get("source"), "local_resource"),
                    source_id=source_id,
                    metadata=metadata,
                    active=True,
                )
            )
    return sorted(descriptors, key=lambda item: item.key())


def command_capability_descriptors(
    command_registry: Any,
    extra_specs: Any = None,
) -> List[CapabilityDescriptor]:
    specs_method = getattr(command_registry, "specs", None)
    if callable(specs_method):
        try:
            specs = list(specs_method(extra_specs=extra_specs) or [])
        except TypeError:
            specs = list(specs_method() or [])
    else:
        specs = []
    descriptors = []
    for spec in specs:
        name = _clean_text(getattr(spec, "name", ""))
        if not name:
            continue
        descriptors.append(
            CapabilityDescriptor(
                name=name,
                kind="command",
                source_type="builtin",
                source_id="slash_commands",
                metadata={
                    "usage": str(getattr(spec, "usage", "") or ""),
                    "summary": str(getattr(spec, "summary", "") or ""),
                },
                active=True,
            )
        )
    return descriptors


def command_capability_payload(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    commands = []
    for item in list((snapshot or {}).get("descriptors") or []):
        if not isinstance(item, dict) or item.get("kind") != "command":
            continue
        metadata = dict(item.get("metadata") or {})
        usage = str(metadata.get("usage") or "").strip()
        name = _clean_text(item.get("name"))
        if not name or not usage:
            continue
        commands.append(
            {
                "name": name,
                "usage": usage,
                "summary": str(metadata.get("summary") or ""),
                "source_type": _clean_text(item.get("source_type"), "builtin"),
                "source_id": _clean_text(item.get("source_id"), "slash_commands"),
                "active": bool(item.get("active")),
            }
        )
    commands.sort(key=lambda item: item["usage"])
    return {"commands": commands}


def mode_capability_descriptors(profile: Any) -> List[CapabilityDescriptor]:
    payloads_method = getattr(profile, "mode_descriptor_payloads", None)
    if not callable(payloads_method):
        return []
    descriptors = []
    for item in list(payloads_method() or []):
        if not isinstance(item, dict):
            continue
        mode_id = _clean_text(item.get("id"))
        if not mode_id:
            continue
        descriptors.append(
            CapabilityDescriptor(
                name=mode_id,
                kind="mode",
                source_type=_clean_text(item.get("source_type"), "agent_profile"),
                source_id=_clean_text(item.get("source_id"), "agent_profile"),
                metadata=dict(item),
                active=True,
            )
        )
    return sorted(descriptors, key=lambda descriptor: descriptor.name)


def app_capability_payload(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    payload = command_capability_payload(snapshot)
    modes = []
    for item in list((snapshot or {}).get("descriptors") or []):
        if not isinstance(item, dict) or item.get("kind") != "mode":
            continue
        metadata = dict(item.get("metadata") or {})
        mode_id = _clean_text(metadata.get("id") or item.get("name"))
        if not mode_id:
            continue
        try:
            mode_order = int(metadata.get("order") or 0)
        except (TypeError, ValueError):
            mode_order = 0
        modes.append(
            {
                "_order": mode_order,
                "id": mode_id,
                "label": _clean_text(metadata.get("label"), mode_id),
                "description": str(metadata.get("description") or ""),
                "icon_key": _clean_text(metadata.get("icon_key"), "circle"),
                "color_token": _clean_text(metadata.get("color_token"), "info"),
                "command_id": _clean_text(metadata.get("command_id"), "mode.%s" % mode_id),
                "dispatch": dict(metadata.get("dispatch") or {"kind": "mode.set", "mode": mode_id}),
                "source_type": _clean_text(item.get("source_type"), "agent_profile"),
                "source_id": _clean_text(item.get("source_id"), "agent_profile"),
                "active": bool(item.get("active")),
            }
        )
    modes.sort(key=lambda item: (item.get("_order", 0), item["id"]))
    for item in modes:
        item.pop("_order", None)
    payload["modes"] = modes
    workflow_packages = []
    for item in list((snapshot or {}).get("descriptors") or []):
        if not isinstance(item, dict) or item.get("kind") != "workflow_package":
            continue
        metadata = dict(item.get("metadata") or {})
        package_id = _clean_text(metadata.get("package_id") or item.get("name"))
        if not package_id:
            continue
        workflow_packages.append(
            {
                "id": package_id,
                "label": _clean_text(metadata.get("label"), package_id),
                "active": bool(item.get("active")),
                "state": dict(metadata.get("state") or {}),
                "source_type": _clean_text(item.get("source_type"), "workflow_package"),
                "source_id": _clean_text(item.get("source_id"), package_id),
            }
        )
    workflow_packages.sort(key=lambda item: item["id"])
    payload["workflowPackages"] = workflow_packages
    return payload


def workflow_package_capability_descriptors(manifests: Any) -> List[CapabilityDescriptor]:
    descriptors = []
    for manifest in list(manifests or []):
        if hasattr(manifest, "to_dict"):
            payload = manifest.to_dict()
        elif isinstance(manifest, dict):
            payload = dict(manifest)
        else:
            continue
        name = _clean_text(payload.get("package_id"))
        if not name:
            continue
        descriptors.append(
            CapabilityDescriptor(
                name=name,
                kind="workflow_package",
                source_type=_clean_text(payload.get("source_type"), "workflow_package"),
                source_id=_clean_text(payload.get("source_id"), name),
                metadata=payload,
                active=True,
            )
        )
    return sorted(descriptors, key=lambda item: item.key())


def model_profile_capability_descriptor(config_or_client: Any) -> CapabilityDescriptor:
    model = ""
    base_url = ""
    if isinstance(config_or_client, dict):
        model = _clean_text(config_or_client.get("model"))
        base_url = _clean_text(config_or_client.get("base_url"))
    else:
        model = _clean_text(getattr(config_or_client, "model", ""))
        base_url = _clean_text(getattr(config_or_client, "base_url", ""))
    metadata = {}
    if base_url:
        metadata["base_url"] = base_url
    return CapabilityDescriptor(
        name=model or "default-model",
        kind="model_profile",
        source_type="configured",
        source_id="llm",
        metadata=metadata,
        active=True,
    )
