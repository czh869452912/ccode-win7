from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping

from embedagent_protocol.versions import FRONTEND_PROTOCOL_SCHEMA_VERSION


@dataclass(frozen=True)
class WorkspaceChangedNotification(object):
    schema_version: int
    workspace_id: str
    path: str
    reason: str

    def __post_init__(self) -> None:
        if self.schema_version != FRONTEND_PROTOCOL_SCHEMA_VERSION:
            raise ValueError("schema_version must be %s" % FRONTEND_PROTOCOL_SCHEMA_VERSION)
        for field_name in ("workspace_id", "path", "reason"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError("workspace notification %s must be non-blank" % field_name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "workspace_id": self.workspace_id,
            "path": self.path,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "WorkspaceChangedNotification":
        if not isinstance(value, Mapping):
            raise TypeError("workspace notification must be a mapping")
        allowed = {"schema_version", "workspace_id", "path", "reason"}
        unknown = sorted(set(value).difference(allowed))
        if unknown:
            raise ValueError("workspace notification has unknown fields: %s" % ",".join(unknown))
        return cls(
            schema_version=value.get("schema_version"),
            workspace_id=value.get("workspace_id"),
            path=value.get("path"),
            reason=value.get("reason"),
        )
