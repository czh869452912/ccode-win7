from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class AgentModeDescriptor(object):
    slug: str
    label: str
    description: str
    system_prompt: str
    allowed_tools: Tuple[str, ...] = field(default_factory=tuple)
    writable_globs: Tuple[str, ...] = field(default_factory=tuple)
    icon_key: str = "circle"
    color_token: str = "info"

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_tools", tuple(self.allowed_tools or ()))
        object.__setattr__(self, "writable_globs", tuple(self.writable_globs or ()))

    def to_mode_definition(self) -> Dict[str, object]:
        return {
            "slug": self.slug,
            "system_prompt": self.system_prompt,
            "allowed_tools": list(self.allowed_tools),
            "writable_globs": list(self.writable_globs),
            "label": self.label,
            "description": self.description,
            "icon_key": self.icon_key,
            "color_token": self.color_token,
        }

    def to_capability_metadata(self, profile_id: str, order: int = 0) -> Dict[str, object]:
        return {
            "id": self.slug,
            "label": self.label,
            "description": self.description,
            "icon_key": self.icon_key,
            "color_token": self.color_token,
            "order": int(order),
            "command_id": "mode.%s" % self.slug,
            "dispatch": {"kind": "mode.set", "mode": self.slug},
            "source_type": "agent_profile",
            "source_id": profile_id,
        }


@dataclass(frozen=True)
class AgentProfile(object):
    profile_id: str
    label: str
    default_mode: str
    modes: Tuple[AgentModeDescriptor, ...]
    expose_modes: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "modes", tuple(self.modes or ()))

    def mode_registry(self) -> Dict[str, Dict[str, object]]:
        return dict((item.slug, item.to_mode_definition()) for item in self.modes)

    def require_mode(self, mode_name: str) -> AgentModeDescriptor:
        requested = str(mode_name or "").strip()
        for item in self.modes:
            if item.slug == requested:
                return item
        raise ValueError("Unknown mode %r" % (mode_name,))

    def allowed_tools_for(self, mode_name: str) -> List[str]:
        return list(self.require_mode(mode_name).allowed_tools)

    def writable_globs_for(self, mode_name: str) -> List[str]:
        return list(self.require_mode(mode_name).writable_globs)

    def mode_descriptor_payloads(self) -> List[Dict[str, object]]:
        if not self.expose_modes:
            return []
        return [
            item.to_capability_metadata(self.profile_id, order=index)
            for index, item in enumerate(self.modes)
        ]
