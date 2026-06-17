from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from embedagent.compaction_state import CompactionState, CompactionStateReducer
from embedagent.recovery_state import RecoveryState, RecoveryStateReducer
from embedagent.session import (
    Action,
    AssistantReply,
    LoopTransition,
    Observation,
    PendingInteraction,
    Session,
    ToolPresentationSnapshot,
    TranscriptMessage,
)
from embedagent.session_operation_log import OperationLogReducer, OperationLogState

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
    operation_state: OperationLogState = field(default_factory=OperationLogState)
    compaction_state: CompactionState = field(default_factory=CompactionState)
    recovery_state: RecoveryState = field(default_factory=RecoveryState)


class SessionRestorer(object):
    def restore(
        self, events: List[Dict[str, Any]], best_effort: bool = False
    ) -> SessionRestoreResult:
        if not events:
            raise ValueError("cannot restore an empty transcript")
        session_id = str(events[0].get("session_id") or "")
        started_at = str(events[0].get("ts") or "")
        session = Session(session_id=session_id, started_at=started_at or Session().started_at)
        current_mode = "explore"
        seen_turn_ids = set()
        seen_message_ids = set()
        seen_tool_call_ids = set()
        seen_step_ids = set()
        seen_interaction_ids = set()
        seen_boundary_ids = set()
        consumed_event_count = len(events)
        stop_reason = ""
        skipped_count = 0
        skip_reasons: List[Dict[str, Any]] = []

        def _maybe_skip(error_reason: str) -> bool:
            nonlocal skipped_count, skip_reasons, consumed_event_count, stop_reason
            if best_effort and self._should_skip_error(error_reason):
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
            if event_type == "session_meta":
                current_mode = str(payload.get("current_mode") or current_mode)
                if payload.get("started_at"):
                    session.started_at = str(payload["started_at"])
                continue
            # Schema v2 normalized message types
            if event_type in ("user", "assistant", "system", "tool"):
                message_error = self._apply_message(
                    session, payload, seen_turn_ids, seen_message_ids
                )
                if message_error:
                    if _maybe_skip(message_error):
                        continue
                    break
                continue
            if event_type == "message":
                message_error = self._apply_message(
                    session, payload, seen_turn_ids, seen_message_ids
                )
                if message_error:
                    if _maybe_skip(message_error):
                        continue
                    break
                continue
            # Skip lifecycle events that do not carry restore-relevant state
            if event_type in ("tool_use", "command_execution", "interaction"):
                continue
            if event_type in ("operation_started", "operation_finished", "operation_interrupted"):
                continue
            if event_type == "step_started":
                if not session.turns:
                    if _maybe_skip("step_started_without_turn"):
                        continue
                    break
                if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                    if _maybe_skip("step_started_turn_mismatch"):
                        continue
                    break
                step_id = str(payload.get("step_id") or "").strip()
                if step_id and step_id in seen_step_ids:
                    if _maybe_skip("duplicate_step_id"):
                        continue
                    break
                session.begin_step(
                    reasoning=str(payload.get("reasoning") or ""),
                    step_id=step_id,
                )
                if step_id:
                    seen_step_ids.add(step_id)
                continue
            if event_type == "tool_call":
                if session.current_step() is None:
                    if _maybe_skip("tool_call_without_active_step"):
                        continue
                    break
                if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                    if _maybe_skip("tool_call_turn_mismatch"):
                        continue
                    break
                if not self._matches_current_step(session, str(payload.get("step_id") or "")):
                    if _maybe_skip("tool_call_step_mismatch"):
                        continue
                    break
                call_id = str(payload.get("call_id") or "").strip()
                if not call_id or call_id in seen_tool_call_ids:
                    if _maybe_skip("duplicate_tool_call_id"):
                        continue
                    break
                action = Action(
                    name=str(payload.get("tool_name") or ""),
                    arguments=dict(payload.get("arguments") or {}),
                    call_id=call_id,
                )
                presentation = ToolPresentationSnapshot.from_dict(payload.get("presentation"))
                if session._find_tool_call(action.call_id) is None:
                    session.record_tool_call(action, presentation=presentation)
                    seen_tool_call_ids.add(call_id)
                continue
            if event_type == "tool_result":
                # Skip lifecycle tool_result events (they have status field)
                if payload.get("status"):
                    continue
                call_id = str(payload.get("call_id") or "")
                record = session._find_tool_call(call_id) if call_id else None
                if record is None:
                    if _maybe_skip("tool_result_missing_tool_call"):
                        continue
                    break
                parent_message_id = str(payload.get("parent_message_id") or "").strip()
                if parent_message_id and self._message_index(session, parent_message_id) < 0:
                    if _maybe_skip("message_parent_missing"):
                        continue
                    break
                message_id = str(payload.get("message_id") or "").strip()
                if message_id:
                    if message_id in seen_message_ids:
                        if _maybe_skip("duplicate_message_id"):
                            continue
                        break
                    seen_message_ids.add(message_id)
                if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                    if _maybe_skip("tool_result_turn_mismatch"):
                        continue
                    break
                if not self._matches_current_step(session, str(payload.get("step_id") or "")):
                    if _maybe_skip("tool_result_step_mismatch"):
                        continue
                    break
                if not self._matches_tool_result_record(record, payload):
                    if _maybe_skip("tool_result_identity_mismatch"):
                        continue
                    break
                action = Action(
                    name=str(payload.get("tool_name") or ""),
                    arguments=dict(payload.get("arguments") or {}),
                    call_id=call_id,
                )
                observation_payload = dict(payload.get("observation") or {})
                observation = Observation(
                    tool_name=str(payload.get("tool_name") or ""),
                    success=bool(observation_payload.get("success")),
                    error=observation_payload.get("error"),
                    data=observation_payload.get("data"),
                )
                session.add_observation(
                    action,
                    observation,
                    message_id=str(payload.get("message_id") or ""),
                    parent_message_id=parent_message_id,
                    turn_id=str(payload.get("turn_id") or ""),
                    step_id=str(payload.get("step_id") or ""),
                    finished_at=str(payload.get("finished_at") or ""),
                    replaced_by_refs=list(payload.get("replaced_by_refs") or []),
                )
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
            if event_type == "content_replacement":
                if not self._is_valid_content_replacement(session, payload):
                    if _maybe_skip("content_replacement_target_mismatch"):
                        continue
                    break
                session.record_content_replacement(dict(payload))
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
            if event_type == "loop_transition":
                if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                    if _maybe_skip("loop_transition_turn_mismatch"):
                        continue
                    break
                if not self._matches_current_step(session, str(payload.get("step_id") or "")):
                    if _maybe_skip("loop_transition_step_mismatch"):
                        continue
                    break
                pending = session.pending_interaction
                transition = LoopTransition(
                    reason=str(payload.get("reason") or ""),
                    message=str(payload.get("message") or ""),
                    pending_interaction=pending,
                    next_mode=str(payload.get("next_mode") or ""),
                    turns_used=int(payload.get("turns_used") or 0),
                    metadata=dict(payload.get("metadata") or {}),
                )
                session.record_transition(transition)
                if transition.next_mode:
                    current_mode = transition.next_mode
        consumed_events = events[:consumed_event_count]
        operation_state = OperationLogReducer().reduce(consumed_events)
        compaction_state = CompactionStateReducer().reduce(consumed_events)
        recovery_state = RecoveryStateReducer().reduce(consumed_events)
        return SessionRestoreResult(
            session=session,
            current_mode=current_mode,
            transcript_event_count=len(events),
            consumed_event_count=consumed_event_count,
            stop_reason=stop_reason,
            skipped_count=skipped_count,
            skip_reasons=skip_reasons,
            operation_state=operation_state,
            compaction_state=compaction_state,
            recovery_state=recovery_state,
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

    def _apply_message(
        self, session: Session, payload: Dict[str, Any], seen_turn_ids: set, seen_message_ids: set
    ) -> str:
        role = str(payload.get("role") or "")
        message_id = str(payload.get("message_id") or "").strip()
        parent_message_id = str(payload.get("parent_message_id") or "").strip()
        if parent_message_id and self._message_index(session, parent_message_id) < 0:
            return "message_parent_missing"
        if message_id:
            if message_id in seen_message_ids:
                return "duplicate_message_id"
            seen_message_ids.add(message_id)
        if role == "system":
            session.add_system_message(
                str(payload.get("content") or ""),
                message_id=message_id,
                parent_message_id=parent_message_id,
                turn_id=str(payload.get("turn_id") or ""),
                step_id=str(payload.get("step_id") or ""),
                kind=str(payload.get("kind") or "message"),
                metadata=dict(payload.get("metadata") or {}),
                replaced_by_refs=list(payload.get("replaced_by_refs") or []),
            )
            return ""
        if role == "user":
            turn_id = str(payload.get("turn_id") or "").strip()
            if turn_id:
                if turn_id in seen_turn_ids:
                    return "duplicate_turn_id"
                seen_turn_ids.add(turn_id)
            session.add_user_message(
                str(payload.get("content") or ""),
                turn_id=turn_id,
                message_id=message_id,
                parent_message_id=parent_message_id,
            )
            return ""
        if role == "assistant":
            if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                return "assistant_message_turn_mismatch"
            if not self._matches_message_step(session, str(payload.get("step_id") or "")):
                return "assistant_message_step_mismatch"
            reply = AssistantReply(
                content=str(payload.get("content") or ""),
                actions=[
                    Action(
                        name=str(item.get("name") or ""),
                        arguments=dict(item.get("arguments") or {}),
                        call_id=str(item.get("call_id") or ""),
                    )
                    for item in payload.get("actions") or []
                ],
                finish_reason=str(payload.get("finish_reason") or ""),
                reasoning_content=str(payload.get("reasoning_content") or ""),
            )
            session.add_assistant_reply(
                reply,
                message_id=message_id,
                parent_message_id=parent_message_id,
                turn_id=str(payload.get("turn_id") or ""),
                step_id=str(payload.get("step_id") or ""),
            )
            return ""
        if role == "tool":
            if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                return "tool_message_turn_mismatch"
            if not self._matches_message_step(session, str(payload.get("step_id") or "")):
                return "tool_message_step_mismatch"
            message = TranscriptMessage(
                role="tool",
                content=str(payload.get("content") or ""),
                name=str(payload.get("tool_name") or ""),
                tool_call_id=str(payload.get("tool_call_id") or ""),
                message_id=message_id,
                parent_message_id=parent_message_id,
                turn_id=str(payload.get("turn_id") or ""),
                step_id=str(payload.get("step_id") or ""),
                kind=str(payload.get("kind") or "tool_result"),
                metadata=dict(payload.get("metadata") or {}),
                replaced_by_refs=list(payload.get("replaced_by_refs") or []),
            )
            session.messages.append(message)
            if session.turns:
                session.turns[-1].message_end_index = len(session.messages) - 1
            return ""
        return "unknown_message_role"

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

    def _matches_message_step(self, session: Session, step_id: str) -> bool:
        expected = str(step_id or "").strip()
        if not expected:
            return True
        step = session.current_step()
        if step is None:
            return True
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

    def _matches_tool_result_record(self, record: Any, payload: Dict[str, Any]) -> bool:
        tool_name = str(payload.get("tool_name") or "").strip()
        if tool_name and tool_name != str(getattr(record, "tool_name", "") or ""):
            return False
        if "arguments" in payload:
            arguments = payload.get("arguments")
            if isinstance(arguments, dict):
                if dict(arguments) != dict(getattr(record, "arguments", {}) or {}):
                    return False
        return True

    def _is_valid_content_replacement(self, session: Session, payload: Dict[str, Any]) -> bool:
        message_id = str(payload.get("message_id") or "").strip()
        if not message_id:
            return False
        target = None
        for message in session.messages:
            if str(getattr(message, "message_id", "") or "") == message_id:
                target = message
                break
        if target is None or str(getattr(target, "role", "") or "") != "tool":
            return False
        tool_call_id = str(payload.get("tool_call_id") or "").strip()
        if tool_call_id and tool_call_id != str(getattr(target, "tool_call_id", "") or ""):
            return False
        tool_name = str(payload.get("tool_name") or "").strip()
        if tool_name and tool_name != str(getattr(target, "name", "") or ""):
            return False
        return True
