from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Mapping


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("%s must be non-blank" % field_name)
    return value.strip()


def _json_mapping(value: Any, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("%s must be a mapping" % field_name)
    payload = dict(value)
    try:
        json.dumps(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("%s must be JSON-safe" % field_name) from exc
    return payload


@dataclass(frozen=True)
class InteractionProjection(object):
    kind: str
    interaction_id: str
    turn_id: str
    renderer: str
    descriptor_version: int
    descriptor: Dict[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _required_text(self.kind, "interaction.kind"))
        object.__setattr__(
            self,
            "interaction_id",
            _required_text(self.interaction_id, "interaction.interaction_id"),
        )
        object.__setattr__(self, "turn_id", _required_text(self.turn_id, "interaction.turn_id"))
        object.__setattr__(self, "renderer", _required_text(self.renderer, "interaction.renderer"))
        if isinstance(self.descriptor_version, bool) or not isinstance(
            self.descriptor_version, int
        ):
            raise ValueError("interaction.descriptor_version must be an integer")
        if self.descriptor_version <= 0:
            raise ValueError("interaction.descriptor_version must be positive")
        object.__setattr__(
            self,
            "descriptor",
            _json_mapping(self.descriptor, "interaction.descriptor"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "interaction_id": self.interaction_id,
            "turn_id": self.turn_id,
            "renderer": self.renderer,
            "descriptor_version": self.descriptor_version,
            "descriptor": dict(self.descriptor),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "InteractionProjection":
        if not isinstance(value, Mapping):
            raise TypeError("interaction projection must be a mapping")
        allowed = {
            "kind",
            "interaction_id",
            "turn_id",
            "renderer",
            "descriptor_version",
            "descriptor",
        }
        unknown = sorted(set(value).difference(allowed))
        if unknown:
            raise ValueError("interaction projection has unknown fields: %s" % ",".join(unknown))
        return cls(
            kind=value.get("kind"),
            interaction_id=value.get("interaction_id"),
            turn_id=value.get("turn_id"),
            renderer=value.get("renderer"),
            descriptor_version=value.get("descriptor_version"),
            descriptor=value.get("descriptor"),
        )
