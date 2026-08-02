from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Optional, Tuple

from embedagent_core.agent_effects import (
    AgentEffect,
    AgentEffectResult,
    AssembleContextEffect,
    ContextAssembled,
    EffectFailed,
    ExecutePreparedToolBatchEffect,
    FrozenToolAction,
    InteractionSuspended,
    PreparedToolInvocation,
    PrepareToolBatchEffect,
    ProviderCompleted,
    RequestProviderEffect,
    ToolBatchCompleted,
    ToolBatchPrepared,
)
from embedagent_core.agent_lifecycle import AgentLifecycleJournal
from embedagent_core.session import (
    Action,
    AssistantReply,
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
    assistant_message_id: str = ""
    tool_invocation_ids: Tuple[str, ...] = field(default_factory=tuple)
    turn_id: str = ""
    step_id: str = ""
    mode_name: str = ""
    tool_call_ids: Tuple[str, ...] = field(default_factory=tuple)
    workflow_state: str = ""
    source: str = ""
    stream: bool = False
    continuation: str = "context"


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
    """Internal lifecycle kernel behind the session transaction boundary."""

    def __init__(self, lifecycle: Optional[AgentLifecycleJournal] = None) -> None:
        self.lifecycle = lifecycle

    def start(
        self,
        turn_id: str,
        mode_name: str,
        workflow_state: str,
        source: str,
        stream: bool = False,
        step_index: int = 1,
    ) -> KernelStep:
        step_index = max(1, int(step_index or 1))
        cursor = KernelCursor(
            phase="context",
            expected_effect_id=self._effect_id("context", turn_id, step_index, 0),
            step_index=step_index,
            provider_attempt=0,
            compact_retry_used=False,
            turn_id=turn_id,
            step_id=self._step_id(turn_id, step_index),
            mode_name=mode_name,
            workflow_state=workflow_state,
            source=source,
            stream=stream,
        )
        return KernelStep(
            cursor=cursor,
            events=self._step_started_events(cursor),
            effect=self._context_effect(cursor),
        )

    def command_tool(
        self,
        turn_id: str,
        mode_name: str,
        workflow_state: str,
        action: Action,
        parent_message_id: str,
        step_index: int = 1,
    ) -> KernelStep:
        step_index = max(1, int(step_index or 1))
        effect_id = self._effect_id("tool-prepare", turn_id, step_index, 0)
        cursor = KernelCursor(
            phase="tool_prepare",
            expected_effect_id=effect_id,
            step_index=step_index,
            provider_attempt=0,
            compact_retry_used=False,
            turn_id=turn_id,
            step_id=self._step_id(turn_id, step_index),
            mode_name=mode_name,
            workflow_state=workflow_state,
            source="command",
            tool_call_ids=(action.call_id,),
            continuation="complete",
        )
        assistant_message_id = self._assistant_message_id(cursor)
        cursor = replace(cursor, assistant_message_id=assistant_message_id)
        result = ProviderCompleted(
            effect_id,
            AssistantReply("", actions=[action], finish_reason="tool_calls"),
            parent_message_id=parent_message_id,
        )
        return KernelStep(
            cursor=cursor,
            events=self._step_started_events(cursor)[:2]
            + self._assistant_events(cursor, result, assistant_message_id)
            + self._tool_planned_events(cursor, result)
            + (self._operation_started(cursor, "tool_preparation"),),
            effect=PrepareToolBatchEffect(
                effect_id,
                assistant_message_id,
                (FrozenToolAction.from_action(action),),
                mode_name,
                workflow_state,
                continuation="complete",
            ),
        )

    def resume_preparation(
        self,
        session: Session,
        pending: PendingInteraction,
        resolution: dict,
        preparation: PrepareToolBatchEffect,
        turn_id: str,
        source: str = "resume",
        stream: bool = False,
        step_index: int = 1,
    ) -> KernelStep:
        step_index = max(1, int(step_index or 1))
        effect_id = self._effect_id("tool-prepare", turn_id, step_index, 0)
        effect = replace(preparation, effect_id=effect_id)
        cursor = KernelCursor(
            phase="tool_prepare",
            expected_effect_id=effect_id,
            step_index=step_index,
            provider_attempt=0,
            compact_retry_used=False,
            assistant_message_id=effect.assistant_message_id,
            tool_call_ids=tuple(action.call_id for action in effect.actions),
            turn_id=turn_id,
            step_id=self._step_id(turn_id, step_index),
            mode_name=effect.mode_name,
            workflow_state=effect.workflow_state,
            source=source,
            stream=stream,
            continuation=effect.continuation,
        )
        resolution_intent = self.resolve_pending_interaction(session, pending, resolution)
        resolution_payload = dict(resolution_intent.payload)
        resolution_payload.update({"turn_id": cursor.turn_id, "step_id": cursor.step_id})
        resolution_intent = EventIntent(resolution_intent.event_type, resolution_payload)
        return KernelStep(
            cursor=cursor,
            events=self._step_started_events(cursor)[:2]
            + (
                resolution_intent,
                EventIntent(
                    "operation_finished",
                    {
                        "operation_id": "pending:%s" % pending.interaction_id,
                        "kind": "pending_interaction",
                        "turn_id": cursor.turn_id,
                        "step_id": cursor.step_id,
                        "result": {
                            "resolution_status": "resolved",
                            "kind": pending.kind,
                            "tool_name": pending.tool_name,
                        },
                    },
                ),
                self._operation_started(cursor, "tool_preparation"),
            ),
            effect=effect,
        )

    def accept(self, cursor: KernelCursor, result: AgentEffectResult) -> KernelStep:
        if result.effect_id != cursor.expected_effect_id:
            raise ValueError("effect_result_mismatch")

        if isinstance(result, ContextAssembled):
            return self._accept_context(cursor, result)
        if isinstance(result, ProviderCompleted):
            return self._accept_provider(cursor, result)
        if isinstance(result, ToolBatchPrepared):
            return self._accept_prepared(cursor, result)
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
            effect=RequestProviderEffect(
                effect_id,
                result.snapshot,
                cursor.stream,
                deferred_events=result.deferred_events,
                compaction_generation=result.compaction_generation,
            ),
        )

    def _accept_provider(self, cursor: KernelCursor, result: ProviderCompleted) -> KernelStep:
        assistant_message_id = self._assistant_message_id(cursor)
        events = result.events + self._assistant_events(
            cursor,
            result,
            assistant_message_id,
        )
        if not result.reply.actions:
            empty = not str(result.reply.content or "").strip()
            outcome = LoopTransition(
                "guard_stop" if empty else "completed",
                (
                    "provider returned empty assistant response without tool calls"
                    if empty
                    else result.reply.content
                ),
                next_mode=cursor.mode_name,
                turns_used=cursor.step_index,
                metadata={"empty_response": True} if empty else {},
            )
            return KernelStep(
                cursor=replace(cursor, phase="complete", expected_effect_id=""),
                events=events
                + (self._step_finished(cursor, outcome.reason),)
                + self._transition_events(cursor, outcome),
                outcome=outcome,
            )

        effect_id = self._effect_id(
            "tool-prepare",
            cursor.turn_id,
            cursor.step_index,
            cursor.provider_attempt,
        )
        next_cursor = replace(
            cursor,
            assistant_message_id=assistant_message_id,
            tool_call_ids=tuple(action.call_id for action in result.reply.actions),
            tool_invocation_ids=(),
            phase="tool_prepare",
            expected_effect_id=effect_id,
        )
        return KernelStep(
            cursor=next_cursor,
            events=events
            + self._tool_planned_events(next_cursor, result)
            + (self._operation_started(next_cursor, "tool_preparation"),),
            effect=PrepareToolBatchEffect(
                effect_id,
                assistant_message_id,
                tuple(FrozenToolAction.from_action(action) for action in result.reply.actions),
                cursor.mode_name,
                cursor.workflow_state,
                provider_truncated=(
                    str(result.reply.finish_reason or "").strip().lower() == "length"
                ),
            ),
        )

    def _accept_prepared(self, cursor: KernelCursor, result: ToolBatchPrepared) -> KernelStep:
        preparation_finished = self._operation_finished(cursor, "tool_preparation")
        if not result.invocations:
            observations = tuple(
                item.observation
                for item in sorted(
                    result.immediate_results,
                    key=lambda value: value.source_index,
                )
            )
            return self._advance_after_tools(
                cursor,
                observations,
                result.events + (preparation_finished,),
                result.commit_tokens,
                close_tools=False,
            )

        effect_id = self._effect_id(
            "tools",
            cursor.turn_id,
            cursor.step_index,
            cursor.provider_attempt,
        )
        next_cursor = replace(
            cursor,
            phase="tool_execute",
            expected_effect_id=effect_id,
            tool_call_ids=tuple(invocation.provider_call_id for invocation in result.invocations),
            tool_invocation_ids=tuple(
                invocation.invocation_id for invocation in result.invocations
            ),
        )
        return KernelStep(
            cursor=next_cursor,
            events=result.events
            + (preparation_finished,)
            + self._prepared_tool_started_events(next_cursor, result.invocations)
            + (self._operation_started(next_cursor, "tools"),),
            effect=ExecutePreparedToolBatchEffect(
                effect_id,
                result.invocations,
                immediate_results=result.immediate_results,
            ),
            post_commit_tokens=result.commit_tokens,
        )

    def _accept_tools(self, cursor: KernelCursor, result: ToolBatchCompleted) -> KernelStep:
        return self._advance_after_tools(
            cursor,
            result.observations,
            result.events,
            result.commit_tokens,
            close_tools=True,
        )

    def _advance_after_tools(
        self,
        cursor: KernelCursor,
        observations: Tuple[Any, ...],
        events: Tuple[EventIntent, ...],
        commit_tokens: Tuple[Any, ...],
        close_tools: bool,
    ) -> KernelStep:
        next_mode = cursor.mode_name
        for observation in observations:
            data = observation.data if isinstance(observation.data, dict) else {}
            if data.get("mode_changed") and str(data.get("selected_mode") or "").strip():
                next_mode = str(data.get("selected_mode") or "").strip()
        next_index = cursor.step_index + 1
        effect_id = self._effect_id("context", cursor.turn_id, next_index, cursor.provider_attempt)
        next_cursor = replace(
            cursor,
            phase="context",
            expected_effect_id=effect_id,
            step_index=next_index,
            step_id=self._step_id(cursor.turn_id, next_index),
            mode_name=next_mode,
            assistant_message_id="",
            tool_call_ids=(),
            tool_invocation_ids=(),
        )
        closing_events = (self._operation_finished(cursor, "tools"),) if close_tools else ()
        if cursor.continuation == "complete":
            outcome = LoopTransition(
                "completed",
                "command finished",
                next_mode=next_mode,
                turns_used=cursor.step_index,
            )
            return KernelStep(
                cursor=replace(
                    cursor,
                    phase="complete",
                    expected_effect_id="",
                    mode_name=next_mode,
                ),
                events=events
                + closing_events
                + (self._step_finished(cursor, "completed"),)
                + self._transition_events(cursor, outcome),
                outcome=outcome,
                post_commit_tokens=commit_tokens,
            )
        return KernelStep(
            cursor=next_cursor,
            events=events
            + closing_events
            + (self._step_finished(cursor, "tool_calls"),)
            + self._step_started_events(next_cursor),
            effect=self._context_effect(next_cursor),
            post_commit_tokens=commit_tokens,
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
                self._step_finished(cursor, reason),
                self._operation_finished(
                    cursor,
                    {
                        "tool_prepare": "tool_preparation",
                        "tool_execute": "tools",
                    }.get(cursor.phase, cursor.phase),
                ),
            )
            + self._transition_events(cursor, outcome),
            outcome=outcome,
            post_commit_tokens=result.commit_tokens,
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
            retry = LoopTransition(
                "compact_retry",
                result.message,
                next_mode=cursor.mode_name,
                turns_used=cursor.step_index,
                metadata={
                    "source_mode": cursor.mode_name,
                    "retry_mode": "compact",
                    "error": result.message,
                },
            )
            return KernelStep(
                cursor=next_cursor,
                events=result.events
                + (
                    self._loop_transition(cursor, retry),
                    self._operation_started(
                        next_cursor,
                        "context_assembly",
                        metadata=self._context_operation_metadata(next_cursor, True),
                    ),
                ),
                post_commit_tokens=result.commit_tokens,
                effect=self._context_effect(next_cursor, force_compact=True),
            )

        reason = {
            "cancelled": "aborted",
            "safety_limit": "max_turns",
        }.get(result.error_kind, "guard_stop")
        outcome = LoopTransition(
            reason,
            result.message,
            next_mode=cursor.mode_name,
            turns_used=int(result.metadata.get("turns_used") or cursor.step_index),
            metadata={
                "error_kind": result.error_kind,
                **dict(result.metadata),
            },
        )
        return KernelStep(
            cursor=replace(cursor, phase="failed", expected_effect_id=""),
            events=result.events
            + self._unclosed_failure_operations(cursor, result, reason)
            + (self._step_finished(cursor, reason, interrupted=reason == "aborted"),)
            + self._transition_events(cursor, outcome),
            outcome=outcome,
            post_commit_tokens=result.commit_tokens,
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

    def _step_started_events(self, cursor: KernelCursor) -> Tuple[EventIntent, ...]:
        return (
            EventIntent(
                "step_started",
                {
                    "turn_id": cursor.turn_id,
                    "step_id": cursor.step_id,
                    "step_index": cursor.step_index,
                },
            ),
            EventIntent(
                "operation_started",
                {
                    "operation_id": "step:%s" % cursor.step_id,
                    "kind": "agent_step",
                    "turn_id": cursor.turn_id,
                    "step_id": cursor.step_id,
                    "metadata": {"step_index": cursor.step_index},
                },
            ),
            self._operation_started(
                cursor,
                "context_assembly",
                metadata=self._context_operation_metadata(cursor, False),
            ),
        )

    def _step_finished(
        self,
        cursor: KernelCursor,
        reason: str,
        interrupted: bool = False,
    ) -> EventIntent:
        return EventIntent(
            "operation_interrupted" if interrupted else "operation_finished",
            {
                "operation_id": "step:%s" % cursor.step_id,
                "kind": "agent_step",
                "turn_id": cursor.turn_id,
                "step_id": cursor.step_id,
                "reason": reason if interrupted else "",
                "result": {
                    "reason": reason,
                    "turns_used": cursor.step_index,
                },
            },
        )

    def _unclosed_failure_operations(
        self,
        cursor: KernelCursor,
        result: EffectFailed,
        reason: str,
    ) -> Tuple[EventIntent, ...]:
        closed_ids = set()
        for event in result.events:
            if event.event_type not in ("operation_finished", "operation_interrupted"):
                continue
            operation_id = str(event.payload.get("operation_id") or "")
            if operation_id:
                closed_ids.add(operation_id)

        events = []
        effect_id = str(cursor.expected_effect_id or "")
        if effect_id and effect_id not in closed_ids:
            kind = {
                "context": "context_assembly",
                "provider": "provider_request",
                "tools": "tools",
                "tool_prepare": "tool_preparation",
                "tool_execute": "tools",
            }.get(cursor.phase, cursor.phase)
            events.append(
                EventIntent(
                    "operation_interrupted",
                    {
                        "operation_id": effect_id,
                        "kind": kind,
                        "turn_id": cursor.turn_id,
                        "step_id": cursor.step_id,
                        "reason": reason,
                        "result": {"error_kind": result.error_kind},
                    },
                )
            )

        if cursor.phase == "tool_execute":
            for operation_id, call_id in zip(
                cursor.tool_invocation_ids,
                cursor.tool_call_ids,
            ):
                if operation_id in closed_ids:
                    continue
                events.append(
                    EventIntent(
                        "operation_interrupted",
                        {
                            "operation_id": operation_id,
                            "kind": "tool_call",
                            "turn_id": cursor.turn_id,
                            "step_id": cursor.step_id,
                            "tool_call_id": call_id,
                            "reason": reason,
                            "result": {"error_kind": result.error_kind},
                        },
                    )
                )
        return tuple(events)

    def _assistant_events(
        self,
        cursor: KernelCursor,
        result: ProviderCompleted,
        message_id: str,
    ) -> Tuple[EventIntent, ...]:
        actions = [
            {
                "name": action.name,
                "arguments": dict(action.arguments),
                "call_id": action.call_id,
            }
            for action in result.reply.actions
        ]
        return (
            EventIntent(
                "assistant",
                {
                    "role": "assistant",
                    "content": result.reply.content,
                    "message_id": message_id,
                    "parent_message_id": result.parent_message_id,
                    "turn_id": cursor.turn_id,
                    "step_id": cursor.step_id,
                    "actions": actions,
                    "reasoning_content": result.reply.reasoning_content,
                    "finish_reason": result.reply.finish_reason,
                },
            ),
        )

    def _assistant_message_id(self, cursor: KernelCursor) -> str:
        return "m-assistant-%s-%s-%d" % (
            cursor.turn_id or "turn",
            cursor.step_id or "step",
            cursor.provider_attempt,
        )

    def _tool_planned_events(
        self,
        cursor: KernelCursor,
        result: ProviderCompleted,
    ) -> Tuple[EventIntent, ...]:
        events = []
        for index, action in enumerate(result.reply.actions):
            presentation = (
                dict(result.tool_presentations[index])
                if index < len(result.tool_presentations)
                else {"tool_label": action.name}
            )
            events.append(
                EventIntent(
                    "tool_call",
                    {
                        "turn_id": cursor.turn_id,
                        "step_id": cursor.step_id,
                        "call_id": action.call_id,
                        "tool_name": action.name,
                        "arguments": dict(action.arguments),
                        "status": "pending",
                        "presentation": presentation,
                    },
                )
            )
        return tuple(events)

    def _prepared_tool_started_events(
        self,
        cursor: KernelCursor,
        invocations: Tuple[PreparedToolInvocation, ...],
    ) -> Tuple[EventIntent, ...]:
        events = []
        for invocation in invocations:
            events.append(
                EventIntent(
                    "operation_started",
                    {
                        "operation_id": invocation.invocation_id,
                        "kind": "tool_call",
                        "turn_id": cursor.turn_id,
                        "step_id": cursor.step_id,
                        "tool_call_id": invocation.provider_call_id,
                        "parent_operation_id": "step:%s" % cursor.step_id,
                        "metadata": {
                            "tool_name": invocation.effective_action.name,
                            "invocation_id": invocation.invocation_id,
                            "provider_call_id": invocation.provider_call_id,
                            "permission_category": invocation.permission_category,
                            "presentation": invocation.presentation(),
                            "source_type": invocation.source_type,
                            "source_id": invocation.source_id,
                            "replay_safe": invocation.replay_safe,
                        },
                    },
                )
            )
        return tuple(events)

    def _transition_events(
        self,
        cursor: KernelCursor,
        transition: LoopTransition,
    ) -> Tuple[EventIntent, ...]:
        savepoint_id = "savepoint:%s:%s:%s" % (
            cursor.turn_id or "session",
            cursor.step_id or "turn",
            transition.reason or "transition",
        )
        events = []
        pending = transition.pending_interaction
        if pending is not None and pending.interaction_id:
            request_payload = dict(pending.request_payload or {})
            details = dict(
                request_payload.get("permission") or request_payload.get("request") or {}
            )
            events.append(
                EventIntent(
                    "operation_started",
                    {
                        "operation_id": "pending:%s" % pending.interaction_id,
                        "kind": "pending_interaction",
                        "turn_id": cursor.turn_id,
                        "step_id": cursor.step_id,
                        "parent_operation_id": "step:%s" % cursor.step_id,
                        "metadata": {
                            "kind": pending.kind,
                            "tool_name": pending.tool_name,
                            "interaction_id": pending.interaction_id,
                            "category": str(details.get("category") or ""),
                            "reason": str(details.get("reason") or ""),
                            "question": str(details.get("question") or ""),
                        },
                    },
                )
            )
        events.extend(
            (
                EventIntent(
                    "operation_started",
                    {
                        "operation_id": savepoint_id,
                        "kind": "save_point",
                        "turn_id": cursor.turn_id,
                        "step_id": cursor.step_id,
                        "parent_operation_id": "step:%s" % cursor.step_id,
                        "metadata": {"transition_reason": transition.reason},
                    },
                ),
                self._loop_transition(cursor, transition),
                EventIntent(
                    "operation_finished",
                    {
                        "operation_id": savepoint_id,
                        "kind": "save_point",
                        "turn_id": cursor.turn_id,
                        "step_id": cursor.step_id,
                        "result": {
                            "reason": transition.reason,
                            "message": transition.message,
                            "next_mode": transition.next_mode,
                            "turns_used": transition.turns_used,
                            "metadata": dict(transition.metadata),
                        },
                    },
                ),
            )
        )
        return tuple(events)

    def _step_id(self, turn_id: str, step_index: int) -> str:
        return "step-%s-%d" % (turn_id or "turn", step_index)

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

    def _context_operation_metadata(
        self,
        cursor: KernelCursor,
        force_compact: bool,
    ) -> dict:
        metadata = {
            "mode_name": cursor.mode_name,
            "workflow_state": cursor.workflow_state,
            "force_compact": bool(force_compact),
        }
        if cursor.source:
            metadata["source"] = cursor.source
        return metadata

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
