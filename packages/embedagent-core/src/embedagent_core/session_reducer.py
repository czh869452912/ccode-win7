from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Set

from embedagent_core.compacted_history import CompactedHistoryReducer
from embedagent_core.session import (
    Action,
    AssistantReply,
    CompactBoundary,
    LoopTransition,
    Observation,
    PendingInteraction,
    Session,
    ToolPresentationSnapshot,
    TranscriptMessage,
)


class SessionReduceError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = str(reason or "session_reduce_error")
        super(SessionReduceError, self).__init__(self.reason)


@dataclass
class SessionReducerContext:
    current_mode: str = ""
    seen_turn_ids: Set[str] = field(default_factory=set)
    seen_step_ids: Set[str] = field(default_factory=set)
    seen_message_ids: Set[str] = field(default_factory=set)
    seen_tool_call_ids: Set[str] = field(default_factory=set)
    seen_interaction_ids: Set[str] = field(default_factory=set)
    seen_boundary_ids: Set[str] = field(default_factory=set)
    seen_compacted_history_ids: Set[str] = field(default_factory=set)


class SessionReducer(object):
    _STATE_NEUTRAL_TYPES = frozenset(
        (
            "operation_started",
            "operation_finished",
            "operation_interrupted",
            "tool_use",
            "command_execution",
            "interaction",
            "runtime_configured",
            "resource_discovered",
            "resource_reloaded",
            "recovery_marker",
        )
    )

    def __init__(self) -> None:
        self._handlers = {
            "session_meta": self._apply_session_meta,
            "message": self._apply_message,
            "system": self._apply_message,
            "user": self._apply_message,
            "assistant": self._apply_message,
            "tool": self._apply_message,
            "step_started": self._apply_step_started,
            "loop_transition": self._apply_loop_transition,
            "tool_call": self._apply_tool_call,
            "tool_result": self._apply_tool_result,
            "content_replacement": self._apply_content_replacement,
            "pending_interaction": self._apply_pending_interaction,
            "pending_resolution": self._apply_pending_resolution,
            "workflow_patch": self._apply_workflow_patch,
            "context_snapshot": self._apply_context_snapshot,
            "compact_boundary": self._apply_compact_boundary,
            "compacted_history": self._apply_compacted_history,
        }

    def apply(
        self,
        session: Session,
        context: SessionReducerContext,
        event: Dict[str, Any],
    ) -> None:
        if int(event.get("schema_version") or 0) != 2:
            raise SessionReduceError("unsupported_schema_version")
        if str(event.get("session_id") or "") != session.session_id:
            raise SessionReduceError("session_id_mismatch")
        event_type = str(event.get("type") or "")
        if event_type in self._STATE_NEUTRAL_TYPES:
            return
        handler = self._handlers.get(event_type)
        if handler is None:
            raise SessionReduceError("unknown_event_type")
        if event_type == "compacted_history":
            handler(session, context, dict(event.get("payload") or {}), event)
            return
        handler(session, context, dict(event.get("payload") or {}))

    def _apply_session_meta(
        self,
        session: Session,
        context: SessionReducerContext,
        payload: Dict[str, Any],
    ) -> None:
        context.current_mode = str(payload.get("current_mode") or context.current_mode)
        if payload.get("started_at"):
            session.started_at = str(payload["started_at"])

    def _apply_message(
        self,
        session: Session,
        context: SessionReducerContext,
        payload: Dict[str, Any],
    ) -> None:
        role = str(payload.get("role") or "")
        kind = str(payload.get("kind") or "message")
        if role == "system" and bool(payload.get("replace_kind")):
            for message in session.messages:
                if (
                    str(getattr(message, "role", "") or "") == role
                    and str(getattr(message, "kind", "") or "") == kind
                ):
                    message.archived = True
            if bool(payload.get("remove_only")):
                return
        message_id = str(payload.get("message_id") or "").strip()
        parent_message_id = str(payload.get("parent_message_id") or "").strip()
        if (
            parent_message_id
            and parent_message_id not in context.seen_message_ids
            and self._message_index(session, parent_message_id) < 0
        ):
            raise SessionReduceError("message_parent_missing")
        if message_id and message_id in context.seen_message_ids:
            raise SessionReduceError("duplicate_message_id")
        if role == "system":
            session.add_system_message(
                str(payload.get("content") or ""),
                message_id=message_id,
                parent_message_id=parent_message_id,
                turn_id=str(payload.get("turn_id") or ""),
                step_id=str(payload.get("step_id") or ""),
                kind=kind,
                metadata=dict(payload.get("metadata") or {}),
                replaced_by_refs=list(payload.get("replaced_by_refs") or []),
            )
            if message_id:
                context.seen_message_ids.add(message_id)
            return
        if role == "user":
            turn_id = str(payload.get("turn_id") or "").strip()
            if turn_id and turn_id in context.seen_turn_ids:
                raise SessionReduceError("duplicate_turn_id")
            session.add_user_message(
                str(payload.get("content") or ""),
                turn_id=turn_id,
                message_id=message_id,
                parent_message_id=parent_message_id,
            )
            if turn_id:
                context.seen_turn_ids.add(turn_id)
            if message_id:
                context.seen_message_ids.add(message_id)
            return
        if role == "assistant":
            if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                raise SessionReduceError("assistant_message_turn_mismatch")
            if not self._matches_current_step(session, str(payload.get("step_id") or "")):
                raise SessionReduceError("assistant_message_step_mismatch")
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
                usage=dict((payload.get("metadata") or {}).get("usage") or {}),
            )
            session.add_assistant_reply(
                reply,
                message_id=message_id,
                parent_message_id=parent_message_id,
                turn_id=str(payload.get("turn_id") or ""),
                step_id=str(payload.get("step_id") or ""),
            )
            if message_id:
                context.seen_message_ids.add(message_id)
            return
        if role == "tool":
            if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                raise SessionReduceError("tool_message_turn_mismatch")
            if not self._matches_current_step(session, str(payload.get("step_id") or "")):
                raise SessionReduceError("tool_message_step_mismatch")
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
            if message_id:
                context.seen_message_ids.add(message_id)
            return
        raise SessionReduceError("unknown_message_role")

    def _apply_step_started(
        self,
        session: Session,
        context: SessionReducerContext,
        payload: Dict[str, Any],
    ) -> None:
        if not session.turns:
            raise SessionReduceError("step_started_without_turn")
        if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
            raise SessionReduceError("step_started_turn_mismatch")
        step_id = str(payload.get("step_id") or "").strip()
        if step_id and step_id in context.seen_step_ids:
            raise SessionReduceError("duplicate_step_id")
        session.begin_step(
            reasoning=str(payload.get("reasoning") or ""),
            step_id=step_id,
        )
        if step_id:
            context.seen_step_ids.add(step_id)

    def _apply_loop_transition(
        self,
        session: Session,
        context: SessionReducerContext,
        payload: Dict[str, Any],
    ) -> None:
        if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
            raise SessionReduceError("loop_transition_turn_mismatch")
        if not self._matches_current_step(session, str(payload.get("step_id") or "")):
            raise SessionReduceError("loop_transition_step_mismatch")
        transition = LoopTransition(
            reason=str(payload.get("reason") or ""),
            message=str(payload.get("message") or ""),
            pending_interaction=session.pending_interaction,
            next_mode=str(payload.get("next_mode") or ""),
            turns_used=int(payload.get("turns_used") or 0),
            metadata=dict(payload.get("metadata") or {}),
        )
        session.record_transition(transition)
        if transition.next_mode:
            context.current_mode = transition.next_mode

    def _apply_tool_call(
        self,
        session: Session,
        context: SessionReducerContext,
        payload: Dict[str, Any],
    ) -> None:
        if session.current_step() is None:
            raise SessionReduceError("tool_call_without_active_step")
        if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
            raise SessionReduceError("tool_call_turn_mismatch")
        if not self._matches_current_step(session, str(payload.get("step_id") or "")):
            raise SessionReduceError("tool_call_step_mismatch")
        call_id = str(payload.get("call_id") or "").strip()
        if not call_id or call_id in context.seen_tool_call_ids:
            raise SessionReduceError("duplicate_tool_call_id")
        action = Action(
            name=str(payload.get("tool_name") or ""),
            arguments=dict(payload.get("arguments") or {}),
            call_id=call_id,
        )
        presentation = ToolPresentationSnapshot.from_dict(payload.get("presentation"))
        record = session._find_tool_call(call_id)
        if record is None:
            session.record_tool_call(action, presentation=presentation)
        else:
            record.presentation = presentation
        context.seen_tool_call_ids.add(call_id)

    def _apply_tool_result(
        self,
        session: Session,
        context: SessionReducerContext,
        payload: Dict[str, Any],
    ) -> None:
        if payload.get("status"):
            return
        call_id = str(payload.get("call_id") or "")
        record = session._find_tool_call(call_id) if call_id else None
        if record is None:
            raise SessionReduceError("tool_result_missing_tool_call")
        parent_message_id = str(payload.get("parent_message_id") or "").strip()
        if (
            parent_message_id
            and parent_message_id not in context.seen_message_ids
            and self._message_index(session, parent_message_id) < 0
        ):
            raise SessionReduceError("message_parent_missing")
        message_id = str(payload.get("message_id") or "").strip()
        if message_id and message_id in context.seen_message_ids:
            raise SessionReduceError("duplicate_message_id")
        if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
            raise SessionReduceError("tool_result_turn_mismatch")
        if not self._matches_current_step(session, str(payload.get("step_id") or "")):
            raise SessionReduceError("tool_result_step_mismatch")
        if not self._matches_tool_result_record(record, payload):
            raise SessionReduceError("tool_result_identity_mismatch")
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
            message_id=message_id,
            parent_message_id=parent_message_id,
            turn_id=str(payload.get("turn_id") or ""),
            step_id=str(payload.get("step_id") or ""),
            finished_at=str(payload.get("finished_at") or ""),
            replaced_by_refs=list(payload.get("replaced_by_refs") or []),
        )
        if message_id:
            context.seen_message_ids.add(message_id)

    def _apply_content_replacement(
        self,
        session: Session,
        context: SessionReducerContext,
        payload: Dict[str, Any],
    ) -> None:
        del context
        if not self._is_valid_content_replacement(session, payload):
            raise SessionReduceError("content_replacement_target_mismatch")
        session.record_content_replacement(dict(payload))

    def _apply_pending_interaction(
        self,
        session: Session,
        context: SessionReducerContext,
        payload: Dict[str, Any],
    ) -> None:
        if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
            raise SessionReduceError("pending_interaction_turn_mismatch")
        if not self._matches_current_step(session, str(payload.get("step_id") or "")):
            raise SessionReduceError("pending_interaction_step_mismatch")
        interaction_id = str(payload.get("interaction_id") or "").strip()
        if not interaction_id:
            raise SessionReduceError("interaction_expired")
        interaction_created_at = str(payload.get("created_at") or "").strip()
        if interaction_created_at and self._interaction_is_stale(
            interaction_created_at,
            max_age_seconds=300,
        ):
            raise SessionReduceError("interaction_expired")
        if interaction_id in context.seen_interaction_ids:
            raise SessionReduceError("duplicate_pending_interaction_id")
        pending = PendingInteraction(
            interaction_id=interaction_id,
            kind=str(payload.get("kind") or ""),
            tool_name=str(payload.get("tool_name") or ""),
            request_payload=deepcopy(dict(payload.get("request_payload") or {})),
            created_at=interaction_created_at or "",
        )
        session.pending_interaction = pending
        if session.turns:
            session.turns[-1].pending_interaction = pending
        context.seen_interaction_ids.add(interaction_id)

    def _apply_pending_resolution(
        self,
        session: Session,
        context: SessionReducerContext,
        payload: Dict[str, Any],
    ) -> None:
        del context
        pending = session.pending_interaction
        if pending is None:
            raise SessionReduceError("pending_resolution_without_pending")
        if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
            raise SessionReduceError("pending_resolution_turn_mismatch")
        if not self._matches_current_step(session, str(payload.get("step_id") or "")):
            raise SessionReduceError("pending_resolution_step_mismatch")
        if not self._matches_pending_interaction(pending, payload):
            raise SessionReduceError("pending_resolution_identity_mismatch")
        session.resolve_pending_interaction(deepcopy(dict(payload.get("resolution_payload") or {})))

    def _apply_workflow_patch(
        self,
        session: Session,
        context: SessionReducerContext,
        payload: Dict[str, Any],
    ) -> None:
        del context
        workflow = payload.get("workflow") or {}
        metadata = payload.get("metadata") or {}
        if isinstance(workflow, dict) and workflow:
            session.workflow_state["workflow"] = deepcopy(dict(workflow))
        if isinstance(metadata, dict) and metadata:
            extensions = session.workflow_state.setdefault("extensions", {})
            extensions["last_workflow_patch"] = deepcopy(dict(metadata))

    def _apply_context_snapshot(
        self,
        session: Session,
        context: SessionReducerContext,
        payload: Dict[str, Any],
    ) -> None:
        del context
        session.latest_context_snapshot = deepcopy(payload)

    def _apply_compact_boundary(
        self,
        session: Session,
        context: SessionReducerContext,
        payload: Dict[str, Any],
    ) -> None:
        if not self._is_valid_compact_boundary(session, payload):
            raise SessionReduceError("compact_boundary_invalid_preserved_segment")
        boundary_id = str(payload.get("boundary_id") or "").strip()
        if boundary_id and boundary_id in context.seen_boundary_ids:
            raise SessionReduceError("duplicate_compact_boundary_id")
        boundary_metadata = deepcopy(dict(payload.get("metadata") or {}))
        for metadata_key in ("trigger", "phase", "context_window_generation"):
            if payload.get(metadata_key) is not None:
                boundary_metadata[metadata_key] = deepcopy(payload.get(metadata_key))
        boundary = CompactBoundary(
            boundary_id=boundary_id,
            summary_text=str(payload.get("summary_text") or ""),
            compacted_turn_count=max(0, int(payload.get("compacted_turn_count") or 0)),
            created_at=str(payload.get("created_at") or ""),
            mode_name=str(payload.get("mode_name") or ""),
            preserved_head_message_id=str(payload.get("preserved_head_message_id") or ""),
            preserved_tail_message_id=str(payload.get("preserved_tail_message_id") or ""),
            metadata=boundary_metadata,
        )
        session.compact_boundaries.append(boundary)
        if session.turns:
            session.turns[-1].compact_boundaries.append(boundary)
        summary_message_id = "m-compact-%s" % boundary.boundary_id
        current_step = session.current_step()
        summary_message = TranscriptMessage(
            role="system",
            content=boundary.summary_text,
            message_id=summary_message_id,
            parent_message_id=session.last_message_id(),
            turn_id=session.turns[-1].turn_id if session.turns else "",
            step_id=str(current_step.step_id or "") if current_step is not None else "",
            kind="compact_boundary",
            metadata={
                "boundary_id": boundary.boundary_id,
                "compacted_turn_count": boundary.compacted_turn_count,
                "mode_name": boundary.mode_name,
                "preserved_head_message_id": boundary.preserved_head_message_id,
                "preserved_tail_message_id": boundary.preserved_tail_message_id,
            },
        )
        session.messages.append(summary_message)
        context.seen_message_ids.add(summary_message_id)
        if session.turns:
            session.turns[-1].message_end_index = len(session.messages) - 1
        if boundary_id:
            context.seen_boundary_ids.add(boundary_id)

    def _apply_compacted_history(
        self,
        session: Session,
        context: SessionReducerContext,
        payload: Dict[str, Any],
        event: Dict[str, Any],
    ) -> None:
        compacted_event = dict(event)
        compacted_event["payload"] = deepcopy(payload)
        checkpoint = CompactedHistoryReducer().reduce([compacted_event]).latest_checkpoint
        if checkpoint is None:
            raise SessionReduceError("compacted_history_invalid")
        if not self._is_valid_compacted_history(session, checkpoint):
            raise SessionReduceError("compacted_history_invalid_anchor")
        checkpoint_id = str(checkpoint.checkpoint_id or "")
        if checkpoint_id in context.seen_compacted_history_ids:
            raise SessionReduceError("duplicate_compacted_history_id")
        session.compacted_history.append(checkpoint)
        context.seen_compacted_history_ids.add(checkpoint_id)

    def _is_valid_compact_boundary(self, session: Session, payload: Dict[str, Any]) -> bool:
        head_id = str(payload.get("preserved_head_message_id") or "").strip()
        tail_id = str(payload.get("preserved_tail_message_id") or "").strip()
        if not head_id and not tail_id:
            return True
        if not head_id or not tail_id:
            return False
        head_index = self._message_index(session, head_id)
        tail_index = self._message_index(session, tail_id)
        return head_index >= 0 and tail_index >= 0 and head_index <= tail_index

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
            if role not in ("system", "user", "assistant") or not content:
                return False
        return True

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

    def _message_index(self, session: Session, message_id: str) -> int:
        target = str(message_id or "").strip()
        if not target:
            return -1
        for index, message in enumerate(session.messages):
            if str(getattr(message, "message_id", "") or "") == target:
                return index
        return -1

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

    def _matches_pending_interaction(
        self,
        pending: PendingInteraction,
        payload: Dict[str, Any],
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
