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
        for event in events:
            event_type = str(event.get("type") or "")
            payload = dict(event.get("payload") or {})
            if event_type == "session_meta":
                current_mode = str(payload.get("current_mode") or current_mode)
                if payload.get("started_at"):
                    session.started_at = str(payload["started_at"])
                continue
            if event_type == "message":
                self._apply_message(session, payload)
                continue
            if event_type == "step_started":
                session.begin_step(
                    reasoning=str(payload.get("reasoning") or ""),
                    step_id=str(payload.get("step_id") or ""),
                )
                continue
            if event_type == "tool_call":
                action = Action(
                    name=str(payload.get("tool_name") or ""),
                    arguments=dict(payload.get("arguments") or {}),
                    call_id=str(payload.get("call_id") or ""),
                )
                if session._find_tool_call(action.call_id) is None:
                    session.record_tool_call(action)
                continue
            if event_type == "tool_result":
                call_id = str(payload.get("call_id") or "")
                if not call_id or session._find_tool_call(call_id) is None:
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
                session.resolve_pending_interaction(dict(payload.get("resolution_payload") or {}))
                continue
            if event_type == "content_replacement":
                session.record_content_replacement(dict(payload))
                continue
            if event_type == "context_snapshot":
                session.record_context_snapshot(dict(payload))
                continue
            if event_type == "compact_boundary":
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

    def _apply_message(self, session: Session, payload: Dict[str, Any]) -> None:
        role = str(payload.get("role") or "")
        if role == "system":
            session.add_system_message(
                str(payload.get("content") or ""),
                message_id=str(payload.get("message_id") or ""),
                turn_id=str(payload.get("turn_id") or ""),
                step_id=str(payload.get("step_id") or ""),
                kind=str(payload.get("kind") or "message"),
                metadata=dict(payload.get("metadata") or {}),
                replaced_by_refs=list(payload.get("replaced_by_refs") or []),
            )
            return
        if role == "user":
            session.add_user_message(
                str(payload.get("content") or ""),
                turn_id=str(payload.get("turn_id") or ""),
                message_id=str(payload.get("message_id") or ""),
            )
            return
        if role == "assistant":
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
                message_id=str(payload.get("message_id") or ""),
                turn_id=str(payload.get("turn_id") or ""),
                step_id=str(payload.get("step_id") or ""),
            )
            return
        if role == "tool":
            message = TranscriptMessage(
                role="tool",
                content=str(payload.get("content") or ""),
                name=str(payload.get("tool_name") or ""),
                tool_call_id=str(payload.get("tool_call_id") or ""),
                message_id=str(payload.get("message_id") or ""),
                turn_id=str(payload.get("turn_id") or ""),
                step_id=str(payload.get("step_id") or ""),
                kind=str(payload.get("kind") or "tool_result"),
                metadata=dict(payload.get("metadata") or {}),
                replaced_by_refs=list(payload.get("replaced_by_refs") or []),
            )
            session.messages.append(message)
            if session.turns:
                session.turns[-1].message_end_index = len(session.messages) - 1
