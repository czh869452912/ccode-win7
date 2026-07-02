from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from embedagent.skill_index import build_skill_index
from embedagent_core.capabilities import (
    CapabilityRegistry,
    model_profile_capability_descriptor,
    resource_capability_descriptors,
    runtime_tool_capability_descriptors,
)
from embedagent_core.runtime_config import RuntimeConfigReducer
from embedagent_core.turn_snapshot import TurnSnapshot, TurnSnapshotBuilder


def _has_meaningful_resource_revision(value: Dict[str, Any]) -> bool:
    if not isinstance(value, dict):
        return False
    if int(value.get("revision") or 0) > 0:
        return True
    for key in ("event_id", "reason", "ts"):
        if str(value.get(key) or "").strip():
            return True
    return False


class TurnSnapshotService(object):
    def __init__(self, builder: Optional[TurnSnapshotBuilder] = None) -> None:
        self._builder = builder or TurnSnapshotBuilder()

    def build(self, **kwargs: Any) -> TurnSnapshot:
        return self._builder.build(**kwargs)

    def build_provider_snapshot(
        self,
        session: Any,
        turn_id: str,
        step_id: str,
        mode_name: str,
        workflow_state: str,
        messages: List[Dict[str, Any]],
        tool_schemas: List[Dict[str, Any]],
        tools: Any,
        client: Any,
        transcript_store: Any,
        runtime_config_provider: Optional[Callable[[Any], Dict[str, Any]]] = None,
    ) -> TurnSnapshot:
        active_tool_names = self.active_tool_names_from_schemas(tool_schemas)
        capabilities = self.capability_snapshot_for_provider(tools, client, active_tool_names)
        runtime_config = self.runtime_config_snapshot(
            session,
            transcript_store,
            runtime_config_provider=runtime_config_provider,
        )
        return self.build(
            session_id=session.session_id,
            turn_id=turn_id,
            step_id=step_id,
            mode_name=mode_name,
            workflow_state=workflow_state,
            messages=messages,
            tool_schemas=tool_schemas,
            active_tool_names=active_tool_names,
            model_profile=self.model_profile_snapshot(client, runtime_config),
            resource_revision=self.resource_revision_snapshot(runtime_config),
            prompt_units=self.prompt_units_for_snapshot(tools, runtime_config),
            runtime_environment=self.runtime_environment_snapshot(tools),
            capabilities=capabilities,
            context_stats=self.context_stats_for_snapshot(messages),
        )

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

    def capability_snapshot_for_provider(
        self, tools: Any, client: Any, active_tool_names: List[str]
    ) -> Dict[str, Any]:
        registry = CapabilityRegistry()
        registry.extend(runtime_tool_capability_descriptors(tools))
        local_resources = {}
        local_resources_method = getattr(tools, "local_resources", None)
        if callable(local_resources_method):
            local_resources = local_resources_method()
        registry.extend(resource_capability_descriptors(local_resources))
        registry.register(model_profile_capability_descriptor(client))

        active_set = set(active_tool_names or [])
        for descriptor in registry.descriptors(kind="tool"):
            descriptor.active = descriptor.name in active_set
            registry.register(descriptor)
        return registry.snapshot().to_dict()

    def runtime_config_snapshot(
        self,
        session: Any,
        transcript_store: Any,
        runtime_config_provider: Optional[Callable[[Any], Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if callable(runtime_config_provider):
            try:
                return dict(runtime_config_provider(session) or {})
            except (OSError, RuntimeError, ValueError, TypeError):
                return {}
        try:
            events = transcript_store.load_events(session.session_id)
        except (OSError, ValueError, TypeError):
            return {}
        return RuntimeConfigReducer().reduce(events).to_dict()

    def model_profile_snapshot(
        self, client: Any, runtime_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        config_profile = {}
        if isinstance(runtime_config, dict):
            config_profile = dict(runtime_config.get("model_profile") or {})
        if config_profile:
            return {
                "name": str(config_profile.get("name") or ""),
                "source_type": str(config_profile.get("source_type") or ""),
                "source_id": str(config_profile.get("source_id") or ""),
                "metadata": dict(config_profile.get("metadata") or {}),
            }
        descriptor = model_profile_capability_descriptor(client)
        return {
            "name": descriptor.name,
            "source_type": descriptor.source_type,
            "source_id": descriptor.source_id,
            "metadata": dict(descriptor.metadata or {}),
        }

    def resource_revision_snapshot(
        self, runtime_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not isinstance(runtime_config, dict):
            return {}
        revision = runtime_config.get("resource_revision") or {}
        return dict(revision) if isinstance(revision, dict) else {}

    def prompt_units_for_snapshot(
        self, tools: Any, runtime_config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        local_resources = {}
        local_resources_method = getattr(tools, "local_resources", None)
        if callable(local_resources_method):
            try:
                local_resources = local_resources_method()
            except (OSError, RuntimeError, ValueError, TypeError):
                local_resources = {}
        summary = build_skill_index(local_resources).safe_summary()
        visible_skill_count = int(summary.get("visible_skill_count") or 0)
        if visible_skill_count <= 0:
            return []
        prompt_unit = {
            "kind": "local_skill_listing",
            "visible_skill_names": list(summary.get("visible_skill_names") or []),
            "visible_skill_count": visible_skill_count,
        }
        resource_revision = self.resource_revision_snapshot(runtime_config)
        if _has_meaningful_resource_revision(resource_revision):
            prompt_unit["resource_revision"] = resource_revision
        return [prompt_unit]

    def runtime_environment_snapshot(self, tools: Any) -> Dict[str, Any]:
        runtime_snapshot = getattr(tools, "runtime_environment_snapshot", None)
        if not callable(runtime_snapshot):
            return {}
        return dict(runtime_snapshot() or {})

    def context_stats_for_snapshot(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "message_count": len(messages or []),
        }

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
