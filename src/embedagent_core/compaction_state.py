from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from embedagent_core.compacted_history import CompactedHistoryReducer, CompactedHistoryState


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


def _stable_texts(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    seen = set()
    result = []
    for item in value:
        text = _clean_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return sorted(result)


def _int_counts(value: Any, allowed_keys: List[str]) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result = {}
    for key in allowed_keys:
        if key in value:
            result[key] = _safe_int(value.get(key))
    return result


@dataclass
class CompactionBoundaryRecord(object):
    boundary_id: str
    summary_text: str = ""
    compacted_turn_count: int = 0
    created_at: str = ""
    mode_name: str = ""
    preserved_head_message_id: str = ""
    preserved_tail_message_id: str = ""
    trigger: str = ""
    phase: str = ""
    context_window_generation: int = 0
    token_counts: Dict[str, int] = field(default_factory=dict)
    message_counts: Dict[str, int] = field(default_factory=dict)
    file_activity: Dict[str, List[str]] = field(default_factory=dict)
    evidence_refs: List[str] = field(default_factory=list)
    extension_summary: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    event_id: str = ""
    seq: int = 0
    ts: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_id": self.boundary_id,
            "summary_text": self.summary_text,
            "compacted_turn_count": int(self.compacted_turn_count or 0),
            "created_at": self.created_at,
            "mode_name": self.mode_name,
            "preserved_head_message_id": self.preserved_head_message_id,
            "preserved_tail_message_id": self.preserved_tail_message_id,
            "trigger": self.trigger,
            "phase": self.phase,
            "context_window_generation": int(self.context_window_generation or 0),
            "token_counts": dict(self.token_counts),
            "message_counts": dict(self.message_counts),
            "file_activity": {
                "read_files": list(self.file_activity.get("read_files") or []),
                "modified_files": list(self.file_activity.get("modified_files") or []),
            },
            "evidence_refs": list(self.evidence_refs),
            "extension_summary": bool(self.extension_summary),
            "metadata": _copy_dict(self.metadata),
            "event_id": self.event_id,
            "seq": int(self.seq or 0),
            "ts": self.ts,
        }


@dataclass
class CompactionState(object):
    boundaries: List[CompactionBoundaryRecord] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    compacted_history: CompactedHistoryState = field(default_factory=CompactedHistoryState)

    @property
    def latest_boundary(self) -> Optional[CompactionBoundaryRecord]:
        if not self.boundaries:
            return None
        return self.boundaries[-1]

    def to_dict(self) -> Dict[str, Any]:
        latest = self.latest_boundary
        latest_payload = latest.to_dict() if latest is not None else {}
        summarized_turns = 0
        for record in self.boundaries:
            summarized_turns += int(record.message_counts.get("summarized_turns") or 0)
        return {
            "boundary_count": len(self.boundaries),
            "latest_boundary_id": latest.boundary_id if latest is not None else "",
            "latest_boundary": latest_payload,
            "boundaries": [record.to_dict() for record in self.boundaries],
            "summarized_turn_count": summarized_turns,
            "diagnostics": [dict(item) for item in self.diagnostics],
            "compacted_history": self.compacted_history.to_dict(),
            "status": "ready" if self.boundaries else "empty",
        }


class CompactionStateReducer(object):
    """Reduce compact boundary transcript events into structured diagnostic state."""

    def reduce(self, events: List[Dict[str, Any]]) -> CompactionState:
        state = CompactionState()
        seen_boundary_ids = set()
        for event in list(events or []):
            if not isinstance(event, dict):
                continue
            event_type = _clean_text(event.get("type"))
            if event_type != "compact_boundary":
                continue
            payload = _copy_dict(event.get("payload"))
            boundary_id = _clean_text(payload.get("boundary_id"))
            if not boundary_id:
                state.diagnostics.append(
                    self._diagnostic(event, "missing_boundary_id", boundary_id="")
                )
                continue
            if boundary_id in seen_boundary_ids:
                state.diagnostics.append(
                    self._diagnostic(event, "duplicate_boundary_id", boundary_id=boundary_id)
                )
                continue
            seen_boundary_ids.add(boundary_id)
            state.boundaries.append(self._record_from_payload(boundary_id, payload, event))
        state.compacted_history = CompactedHistoryReducer().reduce(events)
        return state

    def _record_from_payload(
        self, boundary_id: str, payload: Dict[str, Any], event: Dict[str, Any]
    ) -> CompactionBoundaryRecord:
        metadata = _copy_dict(payload.get("metadata"))
        token_counts = _int_counts(payload.get("token_counts"), ["approx_before", "approx_after"])
        message_counts = _int_counts(
            payload.get("message_counts"),
            ["before", "after", "summarized_turns", "recent_turns"],
        )
        file_activity = payload.get("file_activity")
        if not isinstance(file_activity, dict):
            file_activity = {}
        return CompactionBoundaryRecord(
            boundary_id=boundary_id,
            summary_text=_clean_text(payload.get("summary_text")),
            compacted_turn_count=_safe_int(payload.get("compacted_turn_count")),
            created_at=_clean_text(payload.get("created_at")),
            mode_name=_clean_text(payload.get("mode_name")),
            preserved_head_message_id=_clean_text(payload.get("preserved_head_message_id")),
            preserved_tail_message_id=_clean_text(payload.get("preserved_tail_message_id")),
            trigger=_clean_text(payload.get("trigger") or metadata.get("trigger")),
            phase=_clean_text(payload.get("phase") or metadata.get("phase")),
            context_window_generation=_safe_int(
                payload.get("context_window_generation")
                or metadata.get("context_window_generation")
            ),
            token_counts=token_counts,
            message_counts=message_counts,
            file_activity={
                "read_files": _stable_texts(file_activity.get("read_files")),
                "modified_files": _stable_texts(file_activity.get("modified_files")),
            },
            evidence_refs=_stable_texts(payload.get("evidence_refs")),
            extension_summary=bool(payload.get("extension_summary")),
            metadata=metadata,
            event_id=_clean_text(event.get("event_id")),
            seq=_safe_int(event.get("seq")),
            ts=_clean_text(event.get("ts")),
        )

    def _diagnostic(
        self, event: Dict[str, Any], reason: str, boundary_id: str = ""
    ) -> Dict[str, Any]:
        return {
            "reason": reason,
            "boundary_id": boundary_id,
            "event_id": _clean_text(event.get("event_id")),
            "seq": _safe_int(event.get("seq")),
            "ts": _clean_text(event.get("ts")),
        }
