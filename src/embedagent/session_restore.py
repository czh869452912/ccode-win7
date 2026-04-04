from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from embedagent.session import (
    Action,
    AssistantReply,
    LoopTransition,
    Observation,
    PendingInteraction,
    Session,
    TranscriptMessage,
)


@dataclass
class SessionRestoreResult:
    session: Session
    current_mode: str
    transcript_event_count: int


class SessionRestorer(object):
    def restore(self, events: List[Dict[str, Any]]) -> SessionRestoreResult:
        if not events:
            raise ValueError("cannot restore an empty transcript")
        session_id = str(events[0].get("session_id") or "")
        started_at = str(events[0].get("ts") or "")
        session = Session(session_id=session_id, started_at=started_at or Session().started_at)
        current_mode = "explore"
        seen_message_ids = set()
        seen_tool_call_ids = set()
        for event in events:
            event_type = str(event.get("type") or "")
            payload = dict(event.get("payload") or {})
            if event_type == "session_meta":
                current_mode = str(payload.get("current_mode") or current_mode)
                if payload.get("started_at"):
                    session.started_at = str(payload["started_at"])
                continue
            if event_type == "message":
                if not self._apply_message(session, payload, seen_message_ids):
                    break
                continue
            if event_type == "step_started":
                if not session.turns:
                    break
                if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                    break
                session.begin_step(
                    reasoning=str(payload.get("reasoning") or ""),
                    step_id=str(payload.get("step_id") or ""),
                )
                continue
            if event_type == "tool_call":
                if session.current_step() is None:
                    break
                if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                    break
                if not self._matches_current_step(session, str(payload.get("step_id") or "")):
                    break
                call_id = str(payload.get("call_id") or "").strip()
                if not call_id or call_id in seen_tool_call_ids:
                    break
                action = Action(
                    name=str(payload.get("tool_name") or ""),
                    arguments=dict(payload.get("arguments") or {}),
                    call_id=call_id,
                )
                if session._find_tool_call(action.call_id) is None:
                    session.record_tool_call(action)
                    seen_tool_call_ids.add(call_id)
                continue
            if event_type == "tool_result":
                call_id = str(payload.get("call_id") or "")
                if not call_id or session._find_tool_call(call_id) is None:
                    break
                if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                    break
                if not self._matches_current_step(session, str(payload.get("step_id") or "")):
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
                    turn_id=str(payload.get("turn_id") or ""),
                    step_id=str(payload.get("step_id") or ""),
                    finished_at=str(payload.get("finished_at") or ""),
                    replaced_by_refs=list(payload.get("replaced_by_refs") or []),
                )
                continue
            if event_type == "pending_interaction":
                if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                    break
                if not self._matches_current_step(session, str(payload.get("step_id") or "")):
                    break
                pending = PendingInteraction(
                    interaction_id=str(payload.get("interaction_id") or ""),
                    kind=str(payload.get("kind") or ""),
                    tool_name=str(payload.get("tool_name") or ""),
                    request_payload=dict(payload.get("request_payload") or {}),
                )
                session.pending_interaction = pending
                if session.turns:
                    session.turns[-1].pending_interaction = pending
                continue
            if event_type == "pending_resolution":
                if session.pending_interaction is None:
                    break
                if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                    break
                if not self._matches_current_step(session, str(payload.get("step_id") or "")):
                    break
                session.resolve_pending_interaction(dict(payload.get("resolution_payload") or {}))
                continue
            if event_type == "content_replacement":
                session.record_content_replacement(dict(payload))
                continue
            if event_type == "context_snapshot":
                session.record_context_snapshot(dict(payload))
                continue
            if event_type == "compact_boundary":
                if not self._is_valid_compact_boundary(session, payload):
                    break
                session.add_compact_boundary(
                    str(payload.get("summary_text") or ""),
                    int(payload.get("compacted_turn_count") or 0),
                    str(payload.get("mode_name") or ""),
                    dict(payload.get("metadata") or {}),
                    boundary_id=str(payload.get("boundary_id") or ""),
                    created_at=str(payload.get("created_at") or ""),
                    preserved_head_message_id=str(payload.get("preserved_head_message_id") or ""),
                    preserved_tail_message_id=str(payload.get("preserved_tail_message_id") or ""),
                )
                continue
            if event_type == "loop_transition":
                if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                    break
                if not self._matches_current_step(session, str(payload.get("step_id") or "")):
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
        return SessionRestoreResult(
            session=session,
            current_mode=current_mode,
            transcript_event_count=len(events),
        )

    def _apply_message(self, session: Session, payload: Dict[str, Any], seen_message_ids: set) -> bool:
        role = str(payload.get("role") or "")
        message_id = str(payload.get("message_id") or "").strip()
        if message_id:
            if message_id in seen_message_ids:
                return False
            seen_message_ids.add(message_id)
        if role == "system":
            session.add_system_message(
                str(payload.get("content") or ""),
                message_id=message_id,
                turn_id=str(payload.get("turn_id") or ""),
                step_id=str(payload.get("step_id") or ""),
                kind=str(payload.get("kind") or "message"),
                metadata=dict(payload.get("metadata") or {}),
                replaced_by_refs=list(payload.get("replaced_by_refs") or []),
            )
            return True
        if role == "user":
            session.add_user_message(
                str(payload.get("content") or ""),
                turn_id=str(payload.get("turn_id") or ""),
                message_id=message_id,
            )
            return True
        if role == "assistant":
            if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                return False
            if not self._matches_message_step(session, str(payload.get("step_id") or "")):
                return False
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
                turn_id=str(payload.get("turn_id") or ""),
                step_id=str(payload.get("step_id") or ""),
            )
            return True
        if role == "tool":
            if not self._matches_current_turn(session, str(payload.get("turn_id") or "")):
                return False
            if not self._matches_message_step(session, str(payload.get("step_id") or "")):
                return False
            message = TranscriptMessage(
                role="tool",
                content=str(payload.get("content") or ""),
                name=str(payload.get("tool_name") or ""),
                tool_call_id=str(payload.get("tool_call_id") or ""),
                message_id=message_id,
                turn_id=str(payload.get("turn_id") or ""),
                step_id=str(payload.get("step_id") or ""),
                kind=str(payload.get("kind") or "tool_result"),
                metadata=dict(payload.get("metadata") or {}),
                replaced_by_refs=list(payload.get("replaced_by_refs") or []),
            )
            session.messages.append(message)
            if session.turns:
                session.turns[-1].message_end_index = len(session.messages) - 1
            return True
        return False

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
