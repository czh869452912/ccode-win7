from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

MAX_SUMMARY_CHARS = 12000
MAX_REPLACEMENT_MESSAGES = 12
MAX_REPLACEMENT_CONTENT_CHARS = 12000
ALLOWED_REPLACEMENT_ROLES = set(["system", "user", "assistant"])


def _clean_text(value: Any, limit: int = 0) -> str:
    text = str(value or "").strip()
    if limit > 0 and len(text) > limit:
        return text[:limit]
    return text


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _copy_dict(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return deepcopy(value)


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


def _safe_replacement_messages(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    messages = []
    for item in value[:MAX_REPLACEMENT_MESSAGES]:
        if not isinstance(item, dict):
            continue
        role = _clean_text(item.get("role"))
        if role not in ALLOWED_REPLACEMENT_ROLES:
            continue
        content = _clean_text(item.get("content"), MAX_REPLACEMENT_CONTENT_CHARS)
        if not content:
            continue
        message = {
            "role": role,
            "content": content,
        }
        kind = _clean_text(item.get("kind"))
        if kind:
            message["kind"] = kind
        metadata = _copy_dict(item.get("metadata"))
        if metadata:
            message["metadata"] = metadata
        messages.append(message)
    return messages


@dataclass
class CompactedHistoryCheckpoint(object):
    checkpoint_id: str
    boundary_id: str = ""
    summary_text: str = ""
    first_kept_message_id: str = ""
    replacement_messages: List[Dict[str, Any]] = field(default_factory=list)
    trigger: str = ""
    phase: str = ""
    token_counts: Dict[str, int] = field(default_factory=dict)
    message_counts: Dict[str, int] = field(default_factory=dict)
    file_activity: Dict[str, List[str]] = field(default_factory=dict)
    evidence_refs: List[str] = field(default_factory=list)
    extension_summary: bool = False
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    event_id: str = ""
    seq: int = 0
    ts: str = ""

    @property
    def replacement_message_count(self) -> int:
        return len(self.replacement_messages)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "boundary_id": self.boundary_id,
            "summary_text": self.summary_text,
            "first_kept_message_id": self.first_kept_message_id,
            "replacement_messages": [dict(item) for item in self.replacement_messages],
            "replacement_message_count": self.replacement_message_count,
            "trigger": self.trigger,
            "phase": self.phase,
            "token_counts": dict(self.token_counts),
            "message_counts": dict(self.message_counts),
            "file_activity": {
                "read_files": list(self.file_activity.get("read_files") or []),
                "modified_files": list(self.file_activity.get("modified_files") or []),
            },
            "evidence_refs": list(self.evidence_refs),
            "extension_summary": bool(self.extension_summary),
            "created_at": self.created_at,
            "metadata": _copy_dict(self.metadata),
            "event_id": self.event_id,
            "seq": int(self.seq or 0),
            "ts": self.ts,
        }


@dataclass
class CompactedHistoryState(object):
    checkpoints: List[CompactedHistoryCheckpoint] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def latest_checkpoint(self) -> Optional[CompactedHistoryCheckpoint]:
        if not self.checkpoints:
            return None
        return self.checkpoints[-1]

    def to_dict(self) -> Dict[str, Any]:
        latest = self.latest_checkpoint
        return {
            "checkpoint_count": len(self.checkpoints),
            "latest_checkpoint_id": latest.checkpoint_id if latest is not None else "",
            "latest_checkpoint": latest.to_dict() if latest is not None else {},
            "checkpoints": [item.to_dict() for item in self.checkpoints],
            "diagnostics": [dict(item) for item in self.diagnostics],
            "status": "ready" if self.checkpoints else "empty",
        }


class CompactedHistoryReducer(object):
    def reduce(self, events: List[Dict[str, Any]]) -> CompactedHistoryState:
        state = CompactedHistoryState()
        seen_checkpoint_ids = set()
        for event in list(events or []):
            if not isinstance(event, dict):
                continue
            if _clean_text(event.get("type")) != "compacted_history":
                continue
            payload = _copy_dict(event.get("payload"))
            checkpoint_id = _clean_text(payload.get("checkpoint_id"))
            if not checkpoint_id:
                state.diagnostics.append(self._diagnostic(event, "missing_checkpoint_id"))
                continue
            if checkpoint_id in seen_checkpoint_ids:
                state.diagnostics.append(
                    self._diagnostic(
                        event,
                        "duplicate_checkpoint_id",
                        checkpoint_id=checkpoint_id,
                    )
                )
                continue
            replacement_messages = _safe_replacement_messages(payload.get("replacement_messages"))
            if not replacement_messages:
                state.diagnostics.append(
                    self._diagnostic(
                        event,
                        "missing_replacement_messages",
                        checkpoint_id=checkpoint_id,
                    )
                )
                continue
            seen_checkpoint_ids.add(checkpoint_id)
            state.checkpoints.append(
                self._record_from_payload(checkpoint_id, replacement_messages, payload, event)
            )
        return state

    def _record_from_payload(
        self,
        checkpoint_id: str,
        replacement_messages: List[Dict[str, Any]],
        payload: Dict[str, Any],
        event: Dict[str, Any],
    ) -> CompactedHistoryCheckpoint:
        file_activity = payload.get("file_activity")
        if not isinstance(file_activity, dict):
            file_activity = {}
        return CompactedHistoryCheckpoint(
            checkpoint_id=checkpoint_id,
            boundary_id=_clean_text(payload.get("boundary_id")),
            summary_text=_clean_text(payload.get("summary_text"), MAX_SUMMARY_CHARS),
            first_kept_message_id=_clean_text(payload.get("first_kept_message_id")),
            replacement_messages=replacement_messages,
            trigger=_clean_text(payload.get("trigger")),
            phase=_clean_text(payload.get("phase")),
            token_counts=_int_counts(
                payload.get("token_counts"),
                ["approx_before", "approx_after"],
            ),
            message_counts=_int_counts(
                payload.get("message_counts"),
                ["before", "after", "summarized_turns", "recent_turns"],
            ),
            file_activity={
                "read_files": _stable_texts(file_activity.get("read_files")),
                "modified_files": _stable_texts(file_activity.get("modified_files")),
            },
            evidence_refs=_stable_texts(payload.get("evidence_refs")),
            extension_summary=bool(payload.get("extension_summary")),
            created_at=_clean_text(payload.get("created_at")),
            metadata=_copy_dict(payload.get("metadata")),
            event_id=_clean_text(event.get("event_id")),
            seq=_safe_int(event.get("seq")),
            ts=_clean_text(event.get("ts")),
        )

    def _diagnostic(
        self,
        event: Dict[str, Any],
        reason: str,
        checkpoint_id: str = "",
    ) -> Dict[str, Any]:
        return {
            "reason": reason,
            "checkpoint_id": checkpoint_id,
            "event_id": _clean_text(event.get("event_id")),
            "seq": _safe_int(event.get("seq")),
            "ts": _clean_text(event.get("ts")),
        }
