from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_MODEL_PROFILE_KEYS = ("name", "source_type", "source_id", "metadata")


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _copy_dict(value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return deepcopy(value)


def _stable_names(names: Any) -> List[str]:
    if not isinstance(names, list):
        return []
    seen = set()
    result = []
    for item in names:
        name = _clean_text(item)
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return sorted(result)


def _safe_model_profile(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    profile = {}
    for key in _MODEL_PROFILE_KEYS:
        if key not in value:
            continue
        if key == "metadata":
            profile[key] = _copy_dict(value.get(key))
        else:
            text = _clean_text(value.get(key))
            if text:
                profile[key] = text
    return profile


@dataclass
class ResourceRevision(object):
    revision: int = 0
    event_id: str = ""
    seq: int = 0
    ts: str = ""
    reason: str = ""
    counts: Dict[str, Any] = field(default_factory=dict)
    resource_paths: Dict[str, Any] = field(default_factory=dict)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "revision": int(self.revision or 0),
            "event_id": self.event_id,
            "seq": int(self.seq or 0),
            "ts": self.ts,
            "reason": self.reason,
            "counts": _copy_dict(self.counts),
            "resource_paths": _copy_dict(self.resource_paths),
            "diagnostics": [dict(item) for item in list(self.diagnostics or [])],
        }


@dataclass
class ProviderRequestSnapshotRecord(object):
    operation_id: str
    snapshot_id: str = ""
    mode_name: str = ""
    workflow_state: str = ""
    active_tool_names: List[str] = field(default_factory=list)
    model_profile: Dict[str, Any] = field(default_factory=dict)
    capability_counts: Dict[str, Any] = field(default_factory=dict)
    resource_revision: Dict[str, Any] = field(default_factory=dict)
    event_id: str = ""
    seq: int = 0
    ts: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "snapshot_id": self.snapshot_id,
            "mode_name": self.mode_name,
            "workflow_state": self.workflow_state,
            "active_tool_names": list(self.active_tool_names),
            "model_profile": _copy_dict(self.model_profile),
            "capability_counts": _copy_dict(self.capability_counts),
            "resource_revision": _copy_dict(self.resource_revision),
            "event_id": self.event_id,
            "seq": int(self.seq or 0),
            "ts": self.ts,
        }


@dataclass
class RuntimeConfigState(object):
    model_profile: Dict[str, Any] = field(default_factory=dict)
    active_tool_names: List[str] = field(default_factory=list)
    capability_counts: Dict[str, Any] = field(default_factory=dict)
    resource_revision: ResourceRevision = field(default_factory=ResourceRevision)
    provider_requests: List[ProviderRequestSnapshotRecord] = field(default_factory=list)
    last_reason: str = ""
    last_event_id: str = ""
    last_seq: int = 0
    last_ts: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_profile": _copy_dict(self.model_profile),
            "active_tool_names": list(self.active_tool_names),
            "capability_counts": _copy_dict(self.capability_counts),
            "resource_revision": self.resource_revision.to_dict(),
            "provider_requests": [item.to_dict() for item in list(self.provider_requests or [])],
            "last_reason": self.last_reason,
            "last_event_id": self.last_event_id,
            "last_seq": int(self.last_seq or 0),
            "last_ts": self.last_ts,
        }


class RuntimeConfigReducer(object):
    """Reduce transcript events into replayable runtime configuration state."""

    def reduce(self, events: List[Dict[str, Any]]) -> RuntimeConfigState:
        state = RuntimeConfigState()
        for event in list(events or []):
            if not isinstance(event, dict):
                continue
            event_type = _clean_text(event.get("type"))
            payload = _copy_dict(event.get("payload"))
            if event_type == "runtime_configured":
                self._apply_runtime_configured(state, payload, event)
            elif event_type == "resource_reloaded":
                self._apply_resource_reloaded(state, payload, event)
            elif event_type == "operation_started":
                self._apply_provider_request_started(state, payload, event)
        return state

    def _apply_runtime_configured(
        self, state: RuntimeConfigState, payload: Dict[str, Any], event: Dict[str, Any]
    ) -> None:
        model_profile = _safe_model_profile(payload.get("model_profile"))
        if model_profile:
            state.model_profile = model_profile
        if "active_tool_names" in payload:
            state.active_tool_names = _stable_names(payload.get("active_tool_names"))
        if isinstance(payload.get("capability_counts"), dict):
            state.capability_counts = _copy_dict(payload.get("capability_counts"))
        resource_revision = payload.get("resource_revision")
        if isinstance(resource_revision, dict) and "revision" in resource_revision:
            state.resource_revision = self._revision_from_payload(
                resource_revision,
                event,
                revision=int(resource_revision.get("revision") or state.resource_revision.revision),
            )
        self._mark_latest(state, payload, event)

    def _apply_resource_reloaded(
        self, state: RuntimeConfigState, payload: Dict[str, Any], event: Dict[str, Any]
    ) -> None:
        state.resource_revision = self._revision_from_payload(
            payload,
            event,
            revision=state.resource_revision.revision + 1,
        )
        self._mark_latest(state, payload, event)

    def _apply_provider_request_started(
        self, state: RuntimeConfigState, payload: Dict[str, Any], event: Dict[str, Any]
    ) -> None:
        if _clean_text(payload.get("kind")) != "provider_request":
            return
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            return
        snapshot = metadata.get("turn_snapshot")
        if not isinstance(snapshot, dict):
            return
        active_tool_names = _stable_names(snapshot.get("active_tool_names"))
        model_profile = _safe_model_profile(snapshot.get("model_profile"))
        capability_counts = _copy_dict(snapshot.get("capability_counts"))
        state.active_tool_names = active_tool_names
        if model_profile:
            state.model_profile = model_profile
        if capability_counts:
            state.capability_counts = capability_counts
        state.provider_requests.append(
            ProviderRequestSnapshotRecord(
                operation_id=_clean_text(payload.get("operation_id")),
                snapshot_id=_clean_text(snapshot.get("snapshot_id")),
                mode_name=_clean_text(snapshot.get("mode_name")),
                workflow_state=_clean_text(snapshot.get("workflow_state")),
                active_tool_names=active_tool_names,
                model_profile=model_profile,
                capability_counts=capability_counts,
                resource_revision=_copy_dict(snapshot.get("resource_revision")),
                event_id=_clean_text(event.get("event_id")),
                seq=int(event.get("seq") or 0),
                ts=_clean_text(event.get("ts")),
            )
        )

    def _revision_from_payload(
        self, payload: Dict[str, Any], event: Dict[str, Any], revision: int
    ) -> ResourceRevision:
        diagnostics = []
        for item in list(payload.get("diagnostics") or []):
            if isinstance(item, dict):
                diagnostics.append(dict(item))
        return ResourceRevision(
            revision=int(revision or 0),
            event_id=_clean_text(payload.get("event_id") or event.get("event_id")),
            seq=int(payload.get("seq") or event.get("seq") or 0),
            ts=_clean_text(payload.get("ts") or event.get("ts")),
            reason=_clean_text(payload.get("reason")),
            counts=_copy_dict(payload.get("counts")),
            resource_paths=_copy_dict(payload.get("resource_paths")),
            diagnostics=diagnostics,
        )

    def _mark_latest(
        self, state: RuntimeConfigState, payload: Dict[str, Any], event: Dict[str, Any]
    ) -> None:
        state.last_reason = _clean_text(payload.get("reason"))
        state.last_event_id = _clean_text(event.get("event_id"))
        state.last_seq = int(event.get("seq") or 0)
        state.last_ts = _clean_text(event.get("ts"))
