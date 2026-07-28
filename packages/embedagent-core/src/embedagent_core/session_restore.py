from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from embedagent_core.compacted_history import CompactedHistoryReducer
from embedagent_core.compaction_state import CompactionState, CompactionStateReducer
from embedagent_core.recovery_state import RecoveryState, RecoveryStateReducer
from embedagent_core.runtime_config import RuntimeConfigReducer, RuntimeConfigState
from embedagent_core.session import (
    PendingInteraction,
    Session,
)
from embedagent_core.session_operation_log import OperationLogReducer, OperationLogState
from embedagent_core.session_reducer import (
    SessionReduceError,
    SessionReducer,
    SessionReducerContext,
)
from embedagent_core.turn_experience import TurnExperienceReducer, TurnExperienceState

_LOG = logging.getLogger(__name__)


@dataclass
class SessionRestoreResult:
    session: Session
    current_mode: str
    transcript_event_count: int
    consumed_event_count: int
    stop_reason: str = ""
    skipped_count: int = 0
    skip_reasons: List[Dict[str, Any]] = field(default_factory=list)
    reduction_context: SessionReducerContext = field(default_factory=SessionReducerContext)
    operation_state: OperationLogState = field(default_factory=OperationLogState)
    compaction_state: CompactionState = field(default_factory=CompactionState)
    recovery_state: RecoveryState = field(default_factory=RecoveryState)
    runtime_config: RuntimeConfigState = field(default_factory=RuntimeConfigState)
    turn_experience: TurnExperienceState = field(default_factory=TurnExperienceState)


class SessionRestorer(object):
    def restore(
        self,
        events: List[Dict[str, Any]],
        best_effort: bool = False,
        best_effort_event_count: int = 0,
    ) -> SessionRestoreResult:
        if not events:
            raise ValueError("cannot restore an empty transcript")
        session_id = str(events[0].get("session_id") or "")
        started_at = str(events[0].get("ts") or "")
        session = Session(session_id=session_id, started_at=started_at or Session().started_at)
        current_mode = ""
        reducer = SessionReducer()
        reduction_context = SessionReducerContext()
        seen_interaction_ids = reduction_context.seen_interaction_ids
        seen_boundary_ids = reduction_context.seen_boundary_ids
        seen_compacted_history_ids = reduction_context.seen_compacted_history_ids
        consumed_event_count = len(events)
        stop_reason = ""
        skipped_count = 0
        skip_reasons: List[Dict[str, Any]] = []

        def _maybe_skip(error_reason: str) -> bool:
            nonlocal skipped_count, skip_reasons, consumed_event_count, stop_reason
            within_best_effort_history = (
                best_effort_event_count <= 0 or index < best_effort_event_count
            )
            if best_effort and within_best_effort_history and self._should_skip_error(error_reason):
                skipped_count += 1
                skip_reasons.append(
                    {
                        "index": index,
                        "event_type": event_type,
                        "reason": error_reason,
                        "event_id": str(event.get("event_id", "")),
                    }
                )
                _LOG.warning(
                    "Session restore skipped record %d (type=%s, id=%s): %s",
                    index,
                    event_type,
                    event.get("event_id", ""),
                    error_reason,
                )
                return True
            consumed_event_count = index
            stop_reason = error_reason
            return False

        for index, event in enumerate(events):
            event_type = str(event.get("type") or "")
            payload = dict(event.get("payload") or {})
            if event_type in (
                "session_meta",
                "message",
                "user",
                "assistant",
                "system",
                "tool",
                "step_started",
                "tool_call",
                "tool_result",
                "content_replacement",
                "loop_transition",
            ):
                try:
                    reducer_event = dict(event)
                    reducer_event.setdefault("schema_version", 2)
                    reducer_event.setdefault("session_id", session.session_id)
                    reducer.apply(session, reduction_context, reducer_event)
                except SessionReduceError as exc:
                    if _maybe_skip(exc.reason):
                        continue
                    break
                current_mode = reduction_context.current_mode
                continue
            # Skip lifecycle events that do not carry restore-relevant state
            if event_type in ("tool_use", "command_execution", "interaction"):
                continue
            if event_type in ("operation_started", "operation_finished", "operation_interrupted"):
                continue
            if event_type == "pending_interaction":
                if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                    if _maybe_skip("pending_interaction_turn_mismatch"):
                        continue
                    break
                if not self._matches_current_step(session, str(payload.get("step_id") or "")):
                    if _maybe_skip("pending_interaction_step_mismatch"):
                        continue
                    break
                interaction_id = str(payload.get("interaction_id") or "").strip()
                if not interaction_id:
                    if _maybe_skip("interaction_expired"):
                        continue
                    break
                interaction_created_at = str(payload.get("created_at") or "").strip()
                if interaction_created_at and self._interaction_is_stale(
                    interaction_created_at, max_age_seconds=300
                ):
                    if _maybe_skip("interaction_expired"):
                        continue
                    break
                if interaction_id and interaction_id in seen_interaction_ids:
                    if _maybe_skip("duplicate_pending_interaction_id"):
                        continue
                    break
                pending = PendingInteraction(
                    interaction_id=interaction_id,
                    kind=str(payload.get("kind") or ""),
                    tool_name=str(payload.get("tool_name") or ""),
                    request_payload=dict(payload.get("request_payload") or {}),
                    created_at=interaction_created_at or "",
                )
                session.pending_interaction = pending
                if session.turns:
                    session.turns[-1].pending_interaction = pending
                if interaction_id:
                    seen_interaction_ids.add(interaction_id)
                continue
            if event_type == "pending_resolution":
                if session.pending_interaction is None:
                    if _maybe_skip("pending_resolution_without_pending"):
                        continue
                    break
                if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                    if _maybe_skip("pending_resolution_turn_mismatch"):
                        continue
                    break
                if not self._matches_current_step(session, str(payload.get("step_id") or "")):
                    if _maybe_skip("pending_resolution_step_mismatch"):
                        continue
                    break
                if not self._matches_pending_interaction(session.pending_interaction, payload):
                    if _maybe_skip("pending_resolution_identity_mismatch"):
                        continue
                    break
                session.resolve_pending_interaction(dict(payload.get("resolution_payload") or {}))
                continue
            if event_type == "context_snapshot":
                session.record_context_snapshot(dict(payload))
                continue
            if event_type == "workflow_patch":
                workflow = payload.get("workflow") or {}
                metadata = payload.get("metadata") or {}
                if isinstance(workflow, dict) and workflow:
                    session.workflow_state["workflow"] = dict(workflow)
                if isinstance(metadata, dict) and metadata:
                    extensions = session.workflow_state.setdefault("extensions", {})
                    extensions["last_workflow_patch"] = dict(metadata)
                continue
            if event_type == "compact_boundary":
                if not self._is_valid_compact_boundary(session, payload):
                    if _maybe_skip("compact_boundary_invalid_preserved_segment"):
                        continue
                    break
                boundary_id = str(payload.get("boundary_id") or "").strip()
                if boundary_id and boundary_id in seen_boundary_ids:
                    if _maybe_skip("duplicate_compact_boundary_id"):
                        continue
                    break
                boundary_metadata = dict(payload.get("metadata") or {})
                for metadata_key in ("trigger", "phase", "context_window_generation"):
                    if payload.get(metadata_key) is not None:
                        boundary_metadata[metadata_key] = payload.get(metadata_key)
                session.add_compact_boundary(
                    str(payload.get("summary_text") or ""),
                    int(payload.get("compacted_turn_count") or 0),
                    str(payload.get("mode_name") or ""),
                    boundary_metadata,
                    boundary_id=boundary_id,
                    created_at=str(payload.get("created_at") or ""),
                    preserved_head_message_id=str(payload.get("preserved_head_message_id") or ""),
                    preserved_tail_message_id=str(payload.get("preserved_tail_message_id") or ""),
                )
                if boundary_id:
                    seen_boundary_ids.add(boundary_id)
                continue
            if event_type == "compacted_history":
                compacted_history_state = CompactedHistoryReducer().reduce([event])
                checkpoint = compacted_history_state.latest_checkpoint
                if checkpoint is None:
                    if _maybe_skip("compacted_history_invalid"):
                        continue
                    break
                if not self._is_valid_compacted_history(session, checkpoint):
                    if _maybe_skip("compacted_history_invalid_anchor"):
                        continue
                    break
                checkpoint_id = str(getattr(checkpoint, "checkpoint_id", "") or "")
                if checkpoint_id in seen_compacted_history_ids:
                    if _maybe_skip("duplicate_compacted_history_id"):
                        continue
                    break
                session.record_compacted_history(checkpoint)
                seen_compacted_history_ids.add(checkpoint_id)
                continue
        consumed_events = events[:consumed_event_count]
        operation_state = OperationLogReducer().reduce(consumed_events)
        compaction_state = CompactionStateReducer().reduce(consumed_events)
        recovery_state = RecoveryStateReducer().reduce(consumed_events)
        runtime_config = RuntimeConfigReducer().reduce(consumed_events)
        turn_experience = TurnExperienceReducer().reduce(consumed_events)
        return SessionRestoreResult(
            session=session,
            current_mode=current_mode,
            transcript_event_count=len(events),
            consumed_event_count=consumed_event_count,
            stop_reason=stop_reason,
            skipped_count=skipped_count,
            skip_reasons=skip_reasons,
            reduction_context=reduction_context,
            operation_state=operation_state,
            compaction_state=compaction_state,
            recovery_state=recovery_state,
            runtime_config=runtime_config,
            turn_experience=turn_experience,
        )

    def _should_skip_error(self, error_reason: str) -> bool:
        """Determine if an error is skippable in best_effort mode.

        Non-skippable errors (always stop):
        - Empty events list
        - Fundamental session structure corruption

        Skippable errors:
        - turn_mismatch, step_mismatch
        - duplicate IDs
        - missing parent message
        - tool result without tool call
        - stale interaction
        - identity mismatches
        """
        non_skippable = {"empty_transcript"}
        return error_reason not in non_skippable

    def _matches_current_turn(self, session: Session, turn_id: str) -> bool:
        expected = str(turn_id or "").strip()
        if not expected:
            return True
        if not session.turns:
            return False
        return str(session.turns[-1].turn_id or "") == expected

    def _matches_current_step(self, session: Session, step_id: str) -> bool:
        expected = str(step_id or "").strip()
        if not expected:
            return True
        step = session.current_step()
        if step is None:
            return False
        return str(step.step_id or "") == expected

    def _is_valid_compact_boundary(self, session: Session, payload: Dict[str, Any]) -> bool:
        head_id = str(payload.get("preserved_head_message_id") or "").strip()
        tail_id = str(payload.get("preserved_tail_message_id") or "").strip()
        if not head_id and not tail_id:
            return True
        if not head_id or not tail_id:
            return False
        head_index = self._message_index(session, head_id)
        tail_index = self._message_index(session, tail_id)
        if head_index < 0 or tail_index < 0:
            return False
        return head_index <= tail_index

    def _is_valid_compacted_history(self, session: Session, checkpoint: Any) -> bool:
        if not str(getattr(checkpoint, "checkpoint_id", "") or "").strip():
            return False
        replacement_messages = list(getattr(checkpoint, "replacement_messages", []) or [])
        if not replacement_messages:
            return False
        first_kept_message_id = str(getattr(checkpoint, "first_kept_message_id", "") or "").strip()
        if first_kept_message_id and self._message_index(session, first_kept_message_id) < 0:
            return False
        for message in replacement_messages:
            if not isinstance(message, dict):
                return False
            role = str(message.get("role") or "").strip()
            content = str(message.get("content") or "").strip()
            if role not in ("system", "user", "assistant"):
                return False
            if not content:
                return False
        return True

    def _message_index(self, session: Session, message_id: str) -> int:
        target = str(message_id or "").strip()
        if not target:
            return -1
        for index, message in enumerate(session.messages):
            if str(getattr(message, "message_id", "") or "") == target:
                return index
        return -1

    def _matches_pending_interaction(
        self, pending: PendingInteraction, payload: Dict[str, Any]
    ) -> bool:
        interaction_id = str(payload.get("interaction_id") or "").strip()
        if interaction_id and interaction_id != str(pending.interaction_id or ""):
            return False
        tool_name = str(payload.get("tool_name") or "").strip()
        if tool_name and tool_name != str(pending.tool_name or ""):
            return False
        kind = str(payload.get("kind") or "").strip()
        if kind and kind != str(pending.kind or ""):
            return False
        return True

    def _interaction_is_stale(self, created_at: str, max_age_seconds: int) -> bool:
        value = str(created_at or "").strip()
        if not value:
            return True
        try:
            created = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return True
        now = datetime.now(timezone.utc).replace(microsecond=0)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return (now - created).total_seconds() > float(max_age_seconds)
