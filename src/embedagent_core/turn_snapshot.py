from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _copy_dict(value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return deepcopy(value)


def _copy_list(value: Optional[List[Any]]) -> List[Any]:
    if not isinstance(value, list):
        return []
    return deepcopy(value)


def _stable_names(names: Optional[List[str]]) -> List[str]:
    seen = set()
    result = []
    for name in list(names or []):
        text = str(name or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return sorted(result)


@dataclass
class TurnSnapshot:
    snapshot_id: str
    session_id: str
    turn_id: str
    step_id: str
    mode_name: str
    workflow_state: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tool_schemas: List[Dict[str, Any]] = field(default_factory=list)
    active_tool_names: List[str] = field(default_factory=list)
    model_profile: Dict[str, Any] = field(default_factory=dict)
    resource_revision: Dict[str, Any] = field(default_factory=dict)
    prompt_units: List[Dict[str, Any]] = field(default_factory=list)
    runtime_environment: Dict[str, Any] = field(default_factory=dict)
    capabilities: Dict[str, Any] = field(default_factory=dict)
    context_stats: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        self.snapshot_id = str(self.snapshot_id or "").strip() or ("ts-" + uuid.uuid4().hex[:12])
        self.session_id = str(self.session_id or "").strip()
        self.turn_id = str(self.turn_id or "").strip()
        self.step_id = str(self.step_id or "").strip()
        self.mode_name = str(self.mode_name or "").strip()
        self.workflow_state = str(self.workflow_state or "").strip()
        self.messages = _copy_list(self.messages)
        self.tool_schemas = _copy_list(self.tool_schemas)
        self.active_tool_names = _stable_names(self.active_tool_names)
        self.model_profile = _copy_dict(self.model_profile)
        self.resource_revision = _copy_dict(self.resource_revision)
        self.prompt_units = _safe_prompt_units(self.prompt_units)
        self.runtime_environment = _copy_dict(self.runtime_environment)
        self.capabilities = _copy_dict(self.capabilities)
        self.context_stats = _copy_dict(self.context_stats)
        self.created_at = str(self.created_at or "").strip() or _utc_now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "step_id": self.step_id,
            "mode_name": self.mode_name,
            "workflow_state": self.workflow_state,
            "messages": deepcopy(self.messages),
            "tool_schemas": deepcopy(self.tool_schemas),
            "active_tool_names": list(self.active_tool_names),
            "model_profile": deepcopy(self.model_profile),
            "resource_revision": deepcopy(self.resource_revision),
            "prompt_units": deepcopy(self.prompt_units),
            "runtime_environment": deepcopy(self.runtime_environment),
            "capabilities": deepcopy(self.capabilities),
            "context_stats": deepcopy(self.context_stats),
            "created_at": self.created_at,
        }


class TurnSnapshotBuilder(object):
    def build(
        self,
        session_id: str,
        turn_id: str,
        step_id: str,
        mode_name: str,
        workflow_state: str,
        messages: List[Dict[str, Any]],
        tool_schemas: List[Dict[str, Any]],
        active_tool_names: Optional[List[str]] = None,
        model_profile: Optional[Dict[str, Any]] = None,
        resource_revision: Optional[Dict[str, Any]] = None,
        prompt_units: Optional[List[Dict[str, Any]]] = None,
        runtime_environment: Optional[Dict[str, Any]] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        context_stats: Optional[Dict[str, Any]] = None,
    ) -> TurnSnapshot:
        return TurnSnapshot(
            snapshot_id="ts-" + uuid.uuid4().hex[:12],
            session_id=session_id,
            turn_id=turn_id,
            step_id=step_id,
            mode_name=mode_name,
            workflow_state=workflow_state,
            messages=messages,
            tool_schemas=tool_schemas,
            active_tool_names=active_tool_names or [],
            model_profile=model_profile or {},
            resource_revision=resource_revision or {},
            prompt_units=prompt_units or [],
            runtime_environment=runtime_environment or {},
            capabilities=capabilities or {},
            context_stats=context_stats or {},
        )


def _safe_prompt_units(value: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip()
        if not kind:
            continue
        entry = {"kind": kind}  # type: Dict[str, Any]
        if kind == "local_skill_listing":
            names = _stable_names(item.get("visible_skill_names"))  # type: ignore[arg-type]
            entry["visible_skill_names"] = names
            entry["visible_skill_count"] = int(item.get("visible_skill_count") or len(names))
            revision = item.get("resource_revision")
            if isinstance(revision, dict):
                entry["resource_revision"] = _copy_dict(revision)
        result.append(entry)
    return result
