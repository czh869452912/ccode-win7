from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

CAPABILITY_KINDS = ("command", "model_profile", "resource", "tool")


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
