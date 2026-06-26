from __future__ import annotations

from typing import Any, Dict, List, Optional

from embedagent.turn_snapshot import TurnSnapshot, TurnSnapshotBuilder


class TurnSnapshotService(object):
    def __init__(self, builder: Optional[TurnSnapshotBuilder] = None) -> None:
        self._builder = builder or TurnSnapshotBuilder()

    def build(self, **kwargs: Any) -> TurnSnapshot:
        return self._builder.build(**kwargs)

    def active_tool_names_from_schemas(self, tool_schemas: List[Dict[str, Any]]) -> List[str]:
        names = []
        for schema in list(tool_schemas or []):
            if not isinstance(schema, dict):
                continue
            function = schema.get("function")
            if not isinstance(function, dict):
                continue
            name = str(function.get("name") or "").strip()
            if name:
                names.append(name)
        return sorted(set(names))

    def metadata(self, snapshot: TurnSnapshot) -> Dict[str, Any]:
        capabilities = dict(snapshot.capabilities or {})
        return {
            "snapshot_id": snapshot.snapshot_id,
            "mode_name": snapshot.mode_name,
            "workflow_state": snapshot.workflow_state,
            "message_count": len(snapshot.messages or []),
            "tool_schema_count": len(snapshot.tool_schemas or []),
            "active_tool_names": list(snapshot.active_tool_names or []),
            "registered_tool_names": self.registered_tool_names_from_capabilities(capabilities),
            "model_profile": dict(snapshot.model_profile or {}),
            "resource_revision": dict(snapshot.resource_revision or {}),
            "prompt_units": [dict(item) for item in list(snapshot.prompt_units or [])],
            "capability_counts": dict(capabilities.get("counts") or {}),
        }

    def registered_tool_names_from_capabilities(self, capabilities: Dict[str, Any]) -> List[str]:
        names = []
        for item in list(capabilities.get("descriptors") or []):
            if not isinstance(item, dict):
                continue
            if str(item.get("kind") or "") != "tool":
                continue
            name = str(item.get("name") or "").strip()
            if name:
                names.append(name)
        return sorted(set(names))
