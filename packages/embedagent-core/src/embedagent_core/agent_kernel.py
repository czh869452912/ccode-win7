from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Optional, Tuple

from embedagent_core.agent_effects import (
    AgentEffect,
    AgentEffectResult,
    AssembleContextEffect,
    ContextAssembled,
    EffectFailed,
    ExecuteToolBatchEffect,
    InteractionSuspended,
    ProviderCompleted,
    RequestProviderEffect,
    ToolBatchCompleted,
)
from embedagent_core.agent_lifecycle import AgentLifecycleJournal
from embedagent_core.session import (
    Action,
    InteractionCheckpoint,
    LoopTransition,
    PendingInteraction,
    Session,
)
from embedagent_core.session_journal import EventIntent
from embedagent_core.turn_snapshot_service import safe_turn_snapshot_metadata


@dataclass(frozen=True)
class KernelCursor:
    phase: str
    expected_effect_id: str
    step_index: int
    provider_attempt: int
    compact_retry_used: bool
    turn_id: str = ""
    step_id: str = ""
    mode_name: str = ""
    workflow_state: str = ""
    source: str = ""
    stream: bool = False


@dataclass(frozen=True)
class KernelStep:
    cursor: KernelCursor
    events: Tuple[EventIntent, ...]
    effect: Optional[AgentEffect] = None
    outcome: Optional[LoopTransition] = None
    post_commit_tokens: Tuple[Any, ...] = field(default_factory=tuple)


class AgentTurnFrame(object):
    """Lifecycle frame for one user, command, or resume turn."""

    def __init__(
        self,
        lifecycle: AgentLifecycleJournal,
        session: Session,
        turn_id: str,
        current_mode: str,
        workflow_state: str,
    ) -> None:
        self._lifecycle = lifecycle
        self._session = session
        self.turn_id = turn_id
        self.current_mode = current_mode
        self.workflow_state = workflow_state

    def finish(self, transition: LoopTransition) -> None:
        self._lifecycle.emit_turn_finished(
            self._session,
            self.turn_id,
            transition,
            self.current_mode,
            self.workflow_state,
        )

    def interrupt(self, reason: str, error: str = "") -> None:
        self._lifecycle.emit_turn_interrupted(
            self._session,
            self.turn_id,
            reason,
            self.current_mode,
            self.workflow_state,
            error=error,
        )


class AgentKernel(object):
    """Internal lifecycle kernel behind the QueryEngine session facade."""

    def __init__(self, lifecycle: Optional[AgentLifecycleJournal] = None) -> None:
        self.lifecycle = lifecycle

    def start(
        self,
        turn_id: str,
        mode_name: str,
        workflow_state: str,
        source: str,
        stream: bool = False,
    ) -> KernelStep:
        cursor = KernelCursor(
            phase="context",
            expected_effect_id=self._effect_id("context", turn_id, 1, 0),
            step_index=1,
            provider_attempt=0,
            compact_retry_used=False,
            turn_id=turn_id,
            step_id="step-1",
            mode_name=mode_name,
            workflow_state=workflow_state,
            source=source,
            stream=stream,
        )
        return KernelStep(
            cursor=cursor,
            events=(self._operation_started(cursor, "context_assembly"),),
            effect=self._context_effect(cursor),
        )

    def accept(self, cursor: KernelCursor, result: AgentEffectResult) -> KernelStep:
        if result.effect_id != cursor.expected_effect_id:
            raise ValueError("effect_result_mismatch")

        if isinstance(result, ContextAssembled):
            return self._accept_context(cursor, result)
        if isinstance(result, ProviderCompleted):
            return self._accept_provider(cursor, result)
        if isinstance(result, ToolBatchCompleted):
            return self._accept_tools(cursor, result)
        if isinstance(result, InteractionSuspended):
            return self._accept_interaction(cursor, result)
        if isinstance(result, EffectFailed):
            return self._accept_failure(cursor, result)
        raise TypeError("unsupported_agent_effect_result")

    def _accept_context(self, cursor: KernelCursor, result: ContextAssembled) -> KernelStep:
        attempt = cursor.provider_attempt + 1
        effect_id = self._effect_id("provider", cursor.turn_id, cursor.step_index, attempt)
        next_cursor = replace(
            cursor,
            phase="provider",
            expected_effect_id=effect_id,
            provider_attempt=attempt,
        )
        return KernelStep(
            cursor=next_cursor,
            events=result.events
            + (
                self._operation_started(
                    next_cursor,
                    "provider_request",
                    metadata=self._provider_operation_metadata(result.snapshot, cursor.stream),
                ),
            ),
            effect=RequestProviderEffect(effect_id, result.snapshot, cursor.stream),
        )

    def _accept_provider(self, cursor: KernelCursor, result: ProviderCompleted) -> KernelStep:
        events = result.events
        if not result.reply.actions:
            outcome = LoopTransition(
                "completed",
                result.reply.content,
                next_mode=cursor.mode_name,
                turns_used=cursor.step_index,
            )
            return KernelStep(
                cursor=replace(cursor, phase="complete", expected_effect_id=""),
                events=events + (self._loop_transition(cursor, outcome),),
                outcome=outcome,
            )

        effect_id = self._effect_id(
            "tools", cursor.turn_id, cursor.step_index, cursor.provider_attempt
        )
        next_cursor = replace(
            cursor,
            phase="tools",
            expected_effect_id=effect_id,
        )
        return KernelStep(
            cursor=next_cursor,
            events=events + (self._operation_started(next_cursor, "tools"),),
            effect=ExecuteToolBatchEffect(
                effect_id,
                tuple(result.reply.actions),
                cursor.mode_name,
                cursor.workflow_state,
            ),
        )

    def _accept_tools(self, cursor: KernelCursor, result: ToolBatchCompleted) -> KernelStep:
        next_index = cursor.step_index + 1
        effect_id = self._effect_id("context", cursor.turn_id, next_index, cursor.provider_attempt)
        next_cursor = replace(
            cursor,
            phase="context",
            expected_effect_id=effect_id,
            step_index=next_index,
            step_id="step-%d" % next_index,
        )
        return KernelStep(
            cursor=next_cursor,
            events=result.events
            + (
                self._operation_finished(cursor, "tools"),
                self._operation_started(next_cursor, "context_assembly"),
            ),
            effect=self._context_effect(next_cursor),
            post_commit_tokens=result.commit_tokens,
        )

    def _accept_interaction(self, cursor: KernelCursor, result: InteractionSuspended) -> KernelStep:
        reason = "permission_wait" if result.pending.kind == "permission" else "user_input_wait"
        outcome = LoopTransition(
            reason,
            pending_interaction=result.pending,
            next_mode=cursor.mode_name,
            turns_used=cursor.step_index,
        )
        return KernelStep(
            cursor=replace(cursor, phase="suspended", expected_effect_id=""),
            events=result.events
            + (
                self._operation_finished(cursor, cursor.phase),
                self._loop_transition(cursor, outcome),
            ),
            outcome=outcome,
        )

    def _accept_failure(self, cursor: KernelCursor, result: EffectFailed) -> KernelStep:
        if result.error_kind == "context_limit" and not cursor.compact_retry_used:
            effect_id = self._effect_id(
                "context-compact",
                cursor.turn_id,
                cursor.step_index,
                cursor.provider_attempt,
            )
            next_cursor = replace(
                cursor,
                phase="context",
                expected_effect_id=effect_id,
                compact_retry_used=True,
                step_id=cursor.step_id or ("step-%d" % cursor.step_index),
            )
            return KernelStep(
                cursor=next_cursor,
                events=result.events + (self._operation_started(next_cursor, "context_assembly"),),
                effect=self._context_effect(next_cursor, force_compact=True),
            )

        reason = "aborted" if result.error_kind == "cancelled" else "guard_stop"
        outcome = LoopTransition(
            reason,
            result.message,
            next_mode=cursor.mode_name,
            turns_used=cursor.step_index,
            metadata={"error_kind": result.error_kind},
        )
        return KernelStep(
            cursor=replace(cursor, phase="failed", expected_effect_id=""),
            events=result.events + (self._loop_transition(cursor, outcome),),
            outcome=outcome,
        )

    def _context_effect(
        self, cursor: KernelCursor, force_compact: bool = False
    ) -> AssembleContextEffect:
        return AssembleContextEffect(
            cursor.expected_effect_id,
            cursor.turn_id,
            cursor.step_id or ("step-%d" % cursor.step_index),
            cursor.mode_name,
            cursor.workflow_state,
            force_compact=force_compact,
        )

    def _operation_started(
        self,
        cursor: KernelCursor,
        kind: str,
        metadata: Optional[dict] = None,
    ) -> EventIntent:
        return EventIntent(
            "operation_started",
            {
                "operation_id": cursor.expected_effect_id,
                "kind": kind,
                "turn_id": cursor.turn_id,
                "step_id": cursor.step_id,
                "retryable": kind
                in ("context", "provider", "context_assembly", "provider_request"),
                "metadata": dict(metadata or ({"source": cursor.source} if cursor.source else {})),
            },
        )

    def _operation_finished(self, cursor: KernelCursor, kind: str) -> EventIntent:
        return EventIntent(
            "operation_finished",
            {
                "operation_id": cursor.expected_effect_id,
                "kind": kind,
                "turn_id": cursor.turn_id,
                "step_id": cursor.step_id,
                "result": {},
            },
        )

    def _loop_transition(self, cursor: KernelCursor, transition: LoopTransition) -> EventIntent:
        return EventIntent(
            "loop_transition",
            {
                "turn_id": cursor.turn_id,
                "step_id": cursor.step_id,
                "reason": transition.reason,
                "message": transition.message,
                "next_mode": transition.next_mode,
                "turns_used": transition.turns_used,
                "metadata": dict(transition.metadata),
            },
        )

    def _provider_operation_metadata(self, snapshot: Any, stream: bool) -> dict:
        return {
            "mode_name": snapshot.mode_name,
            "workflow_state": snapshot.workflow_state,
            "message_count": len(snapshot.messages),
            "tool_schema_count": len(snapshot.tool_schemas),
            "stream": bool(stream),
            "turn_snapshot": safe_turn_snapshot_metadata(snapshot),
        }

    def _effect_id(self, kind: str, turn_id: str, step_index: int, provider_attempt: int) -> str:
        return "%s:%s:%d:%d" % (
            kind,
            turn_id or "turn",
            step_index,
            provider_attempt,
        )

    def begin_turn(
        self,
        session: Session,
        turn_id: str,
        current_mode: str,
        workflow_state: str,
        source: str,
    ) -> AgentTurnFrame:
        if self.lifecycle is None:
            raise RuntimeError("agent_lifecycle_not_configured")
        self.lifecycle.emit_turn_started(
            session,
            turn_id,
            current_mode,
            workflow_state,
            source,
        )
        return AgentTurnFrame(
            lifecycle=self.lifecycle,
            session=session,
            turn_id=turn_id,
            current_mode=current_mode,
            workflow_state=workflow_state,
        )

    def interaction_checkpoint_payload(
        self,
        session: Session,
        action: Action,
        pending: PendingInteraction,
        request_data: dict = None,
    ) -> dict:
        turn_id = session.turns[-1].turn_id if session.turns else ""
        step = session.current_step()
        step_id = step.step_id if step is not None else ""
        return InteractionCheckpoint(
            action={
                "name": action.name,
                "arguments": dict(action.arguments),
                "call_id": action.call_id,
            },
            turn_id=turn_id,
            step_id=step_id,
            interaction_id=pending.interaction_id,
            kind=pending.kind,
            request_data=dict(request_data or {}),
        ).to_dict()

    def record_pending_permission(
        self,
        session: Session,
        action: Action,
        permission_payload: dict,
        current_mode: str,
        interaction_id: str = "",
    ):
        pending_kwargs = {
            "kind": "permission",
            "tool_name": action.name,
        }
        if interaction_id:
            pending_kwargs["interaction_id"] = interaction_id
        pending = PendingInteraction(**pending_kwargs)
        pending.request_payload = self.interaction_checkpoint_payload(
            session,
            action,
            pending,
            request_data={"permission": permission_payload},
        )
        pending.request_payload["permission"] = dict(permission_payload)
        transition = LoopTransition(
            "permission_wait",
            str(permission_payload.get("reason") or ""),
            pending,
            current_mode,
        )
        turn_id = session.turns[-1].turn_id if session.turns else ""
        step = session.current_step()
        step_id = step.step_id if step is not None else ""
        return (
            EventIntent(
                "pending_interaction",
                {
                    "turn_id": turn_id,
                    "step_id": step_id,
                    "interaction_id": pending.interaction_id,
                    "kind": pending.kind,
                    "tool_name": pending.tool_name,
                    "request_payload": dict(pending.request_payload),
                    "created_at": pending.created_at,
                },
            ),
            transition,
        )

    def record_pending_user_input(
        self,
        session: Session,
        action: Action,
        tool_name: str,
        request_payload: dict,
        message: str,
        current_mode: str,
        interaction_id: str = "",
    ):
        pending_kwargs = {
            "kind": "user_input",
            "tool_name": tool_name,
        }
        if interaction_id:
            pending_kwargs["interaction_id"] = interaction_id
        pending = PendingInteraction(**pending_kwargs)
        pending.request_payload = self.interaction_checkpoint_payload(
            session,
            action,
            pending,
            request_data={"request": request_payload},
        )
        pending.request_payload["request"] = dict(request_payload)
        transition = LoopTransition(
            "user_input_wait",
            message,
            pending,
            current_mode,
        )
        turn_id = session.turns[-1].turn_id if session.turns else ""
        step = session.current_step()
        step_id = step.step_id if step is not None else ""
        return (
            EventIntent(
                "pending_interaction",
                {
                    "turn_id": turn_id,
                    "step_id": step_id,
                    "interaction_id": pending.interaction_id,
                    "kind": pending.kind,
                    "tool_name": pending.tool_name,
                    "request_payload": dict(pending.request_payload),
                    "created_at": pending.created_at,
                },
            ),
            transition,
        )

    def resolve_pending_interaction(
        self,
        session: Session,
        pending: PendingInteraction,
        resolution: dict,
    ) -> EventIntent:
        turn_id = session.turns[-1].turn_id if session.turns else ""
        step_id = session.current_step().step_id if session.current_step() is not None else ""
        return EventIntent(
            "pending_resolution",
            {
                "turn_id": turn_id,
                "step_id": step_id,
                "interaction_id": pending.interaction_id,
                "kind": pending.kind,
                "tool_name": pending.tool_name,
                "resolution_payload": dict(resolution or {}),
            },
        )
