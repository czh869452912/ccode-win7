from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_STATUSES = frozenset(("clean", "partial", "degraded"))


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _copy_dict(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return deepcopy(value)


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_status(value: Any) -> str:
    status = _clean_text(value)
    if status in _STATUSES:
        return status
    return "degraded" if status else "clean"


def _summary_counts(value: Any, keys: List[str]) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result = {}
    for key in keys:
        if key in value:
            result[key] = _safe_int(value.get(key))
    return result


def _runtime_summary(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result = {}
    if "active_tool_count" in value:
        result["active_tool_count"] = _safe_int(value.get("active_tool_count"))
    if "resource_revision" in value:
        result["resource_revision"] = _safe_int(value.get("resource_revision"))
    model_profile_name = _clean_text(value.get("model_profile_name"))
    if model_profile_name:
        result["model_profile_name"] = model_profile_name
    return result


def _safe_skip_reasons(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "index": _safe_int(item.get("index")),
                "event_type": _clean_text(item.get("event_type")),
                "reason": _clean_text(item.get("reason")),
                "event_id": _clean_text(item.get("event_id")),
            }
        )
    return result


@dataclass
class RecoveryMarkerRecord(object):
    marker_id: str
    created_at: str = ""
    reason: str = ""
    status: str = "clean"
    current_mode: str = ""
    trusted_event_count: int = 0
    transcript_event_count: int = 0
    stop_reason: str = ""
    skipped_count: int = 0
    skip_reasons: List[Dict[str, Any]] = field(default_factory=list)
    operation_summary: Dict[str, int] = field(default_factory=dict)
    compaction_summary: Dict[str, Any] = field(default_factory=dict)
    runtime_summary: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    event_id: str = ""
    seq: int = 0
    ts: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "marker_id": self.marker_id,
            "created_at": self.created_at,
            "reason": self.reason,
            "status": self.status,
            "current_mode": self.current_mode,
            "trusted_event_count": int(self.trusted_event_count or 0),
            "transcript_event_count": int(self.transcript_event_count or 0),
            "stop_reason": self.stop_reason,
            "skipped_count": int(self.skipped_count or 0),
            "skip_reasons": [dict(item) for item in self.skip_reasons],
            "operation_summary": dict(self.operation_summary),
            "compaction_summary": _copy_dict(self.compaction_summary),
            "runtime_summary": _copy_dict(self.runtime_summary),
            "metadata": _copy_dict(self.metadata),
            "event_id": self.event_id,
            "seq": int(self.seq or 0),
            "ts": self.ts,
        }


@dataclass
class RecoveryState(object):
    markers: List[RecoveryMarkerRecord] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def latest_marker(self) -> Optional[RecoveryMarkerRecord]:
        if not self.markers:
            return None
        return self.markers[-1]

    def to_dict(self) -> Dict[str, Any]:
        latest = self.latest_marker
        counts = {"clean": 0, "partial": 0, "degraded": 0}
        for marker in self.markers:
            counts[marker.status] = counts.get(marker.status, 0) + 1
        return {
            "marker_count": len(self.markers),
            "latest_marker_id": latest.marker_id if latest is not None else "",
            "latest_marker": latest.to_dict() if latest is not None else {},
            "markers": [marker.to_dict() for marker in self.markers],
            "clean_count": counts.get("clean", 0),
            "partial_count": counts.get("partial", 0),
            "degraded_count": counts.get("degraded", 0),
            "diagnostics": [dict(item) for item in self.diagnostics],
            "status": "ready" if self.markers else "empty",
        }


class RecoveryStateReducer(object):
    """Reduce recovery marker transcript events into structured diagnostic state."""

    def reduce(self, events: List[Dict[str, Any]]) -> RecoveryState:
        state = RecoveryState()
        seen_marker_ids = set()
        for event in list(events or []):
            if not isinstance(event, dict):
                continue
            event_type = _clean_text(event.get("type"))
            if event_type != "recovery_marker":
                continue
            payload = _copy_dict(event.get("payload"))
            marker_id = _clean_text(payload.get("marker_id"))
            if not marker_id:
                state.diagnostics.append(self._diagnostic(event, "missing_marker_id"))
                continue
            if marker_id in seen_marker_ids:
                state.diagnostics.append(
                    self._diagnostic(event, "duplicate_marker_id", marker_id=marker_id)
                )
                continue
            seen_marker_ids.add(marker_id)
            state.markers.append(self._record_from_payload(marker_id, payload, event))
        return state

    def _record_from_payload(
        self, marker_id: str, payload: Dict[str, Any], event: Dict[str, Any]
    ) -> RecoveryMarkerRecord:
        operation_summary = _summary_counts(
            payload.get("operation_summary"),
            ["total_count", "started_count", "finished_count", "interrupted_count"],
        )
        compaction_summary = _summary_counts(payload.get("compaction_summary"), ["boundary_count"])
        compaction_payload = payload.get("compaction_summary")
        if isinstance(compaction_payload, dict):
            latest_boundary_id = _clean_text(compaction_payload.get("latest_boundary_id"))
            if latest_boundary_id:
                compaction_summary["latest_boundary_id"] = latest_boundary_id
        return RecoveryMarkerRecord(
            marker_id=marker_id,
            created_at=_clean_text(payload.get("created_at")),
            reason=_clean_text(payload.get("reason")),
            status=_safe_status(payload.get("status")),
            current_mode=_clean_text(payload.get("current_mode")),
            trusted_event_count=_safe_int(payload.get("trusted_event_count")),
            transcript_event_count=_safe_int(payload.get("transcript_event_count")),
            stop_reason=_clean_text(payload.get("stop_reason")),
            skipped_count=_safe_int(payload.get("skipped_count")),
            skip_reasons=_safe_skip_reasons(payload.get("skip_reasons")),
            operation_summary=operation_summary,
            compaction_summary=compaction_summary,
            runtime_summary=_runtime_summary(payload.get("runtime_summary")),
            metadata=_copy_dict(payload.get("metadata")),
            event_id=_clean_text(event.get("event_id")),
            seq=_safe_int(event.get("seq")),
            ts=_clean_text(event.get("ts")),
        )

    def _diagnostic(
        self, event: Dict[str, Any], reason: str, marker_id: str = ""
    ) -> Dict[str, Any]:
        return {
            "reason": reason,
            "marker_id": marker_id,
            "event_id": _clean_text(event.get("event_id")),
            "seq": _safe_int(event.get("seq")),
            "ts": _clean_text(event.get("ts")),
        }
