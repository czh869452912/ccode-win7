from __future__ import annotations

import threading
import uuid
from typing import Any, Callable, Optional

from embedagent.agent_loop_continuation import (
    CONTINUATION_ABORT,
    CONTINUATION_COMPACT_THEN_CONTINUE,
    CONTINUATION_CONTINUE,
    CONTINUATION_STOP,
    AgentLoopContinuationDecision,
    AgentLoopContinuationFacts,
    AgentLoopContinuationPolicy,
    DefaultAgentLoopContinuationPolicy,
)
from embedagent.guard import LoopGuard
from embedagent.interaction import UserInputRequest, UserInputResponse
from embedagent.llm import ModelClientError
from embedagent.permissions import PermissionRequest
from embedagent.session import (
    Action,
    AssistantReply,
    ContextAssemblyResult,
    LoopTransition,
    Observation,
    QueryTurnResult,
    Session,
)
from embedagent.tool_execution import StreamingToolExecutor, partition_tool_actions


class AgentLoop(object):
    """Owns turn-loop orchestration for one session-scoped agent run."""

    def __init__(
        self,
        max_turns: Optional[int] = None,
        max_parallel_tools: int = 3,
        tool_capabilities: Optional[dict] = None,
        continuation_policy: Optional[AgentLoopContinuationPolicy] = None,
        session_guard: Optional[Callable[[], Any]] = None,
        append_transcript_event: Optional[Callable[..., Any]] = None,
        append_message_event: Optional[Callable[..., Any]] = None,
        emit_operation_started: Optional[Callable[..., Any]] = None,
        emit_lifecycle_event: Optional[Callable[..., Any]] = None,
        emit_step_finished: Optional[Callable[..., Any]] = None,
        turn_id: Optional[Callable[..., Any]] = None,
        record_transition: Optional[Callable[..., Any]] = None,
        build_context_operation: Optional[Callable[..., Any]] = None,
        record_context_snapshot_operation: Optional[Callable[..., Any]] = None,
        persist_summary: Optional[Callable[..., Any]] = None,
        extension_host: Optional[Any] = None,
        call_provider_operation: Optional[Callable[..., Any]] = None,
        should_retry_with_compact: Optional[Callable[..., Any]] = None,
        maybe_record_compact_boundary: Optional[Callable[..., Any]] = None,
        maybe_maintain_memory: Optional[Callable[..., Any]] = None,
        is_completion_signal: Optional[Callable[..., Any]] = None,
        tool_presentation_snapshot: Optional[Callable[..., Any]] = None,
        action_service: Optional[Any] = None,
        record_tool_observation: Optional[Callable[..., Any]] = None,
        discarded_observation: Optional[Callable[..., Any]] = None,
        interrupted_observation: Optional[Callable[..., Any]] = None,
        is_interrupted_observation: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.loop_safety_limit = self._normalize_safety_limit(max_turns)
        self.max_turns = self.loop_safety_limit
        self.max_parallel_tools = max(1, int(max_parallel_tools or 1))
        self.tool_capabilities = tool_capabilities or {}
        self.continuation_policy = continuation_policy or DefaultAgentLoopContinuationPolicy()
        self._session_guard = session_guard
        self._append_transcript_event = append_transcript_event
        self._append_message_event = append_message_event
        self._emit_operation_started = emit_operation_started
        self._emit_lifecycle_event = emit_lifecycle_event
        self._emit_step_finished = emit_step_finished
        self._turn_id = turn_id
        self._record_transition = record_transition
        self._build_context_operation = build_context_operation
        self._record_context_snapshot_operation = record_context_snapshot_operation
        self._persist_summary = persist_summary
        self._extension_host = extension_host
        self._call_provider_operation = call_provider_operation
        self._should_retry_with_compact = should_retry_with_compact
        self._maybe_record_compact_boundary = maybe_record_compact_boundary
        self._maybe_maintain_memory = maybe_maintain_memory
        self._is_completion_signal = is_completion_signal
        self._tool_presentation_snapshot = tool_presentation_snapshot
        self._action_service = action_service
        self._record_tool_observation = record_tool_observation
        self._discarded_observation = discarded_observation
        self._interrupted_observation = interrupted_observation
        self._is_interrupted_observation = is_interrupted_observation

    @staticmethod
    def _normalize_safety_limit(value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        limit = int(value)
        if limit <= 0:
            return None
        return limit

    def _safety_limit_reached(self, completed_steps: int) -> bool:
        return (
            self.loop_safety_limit is not None
            and int(completed_steps or 0) >= self.loop_safety_limit
        )

    @staticmethod
    def _has_visible_content(reply: AssistantReply) -> bool:
        return bool(str(reply.content or "").strip())

    def _transition_from_decision(
        self,
        decision: AgentLoopContinuationDecision,
        fallback_reason: str,
        fallback_message: str,
        turns_used: int,
        fallback_next_mode: str = "",
    ) -> LoopTransition:
        return LoopTransition(
            reason=decision.reason or fallback_reason,
            message=decision.message or fallback_message,
            next_mode=decision.next_mode or fallback_next_mode,
            turns_used=turns_used,
            metadata=dict(decision.metadata or {}),
        )

    def _ensure_configured(self) -> None:
        required = (
            "_session_guard",
            "_append_transcript_event",
            "_append_message_event",
            "_emit_operation_started",
            "_emit_lifecycle_event",
            "_emit_step_finished",
            "_turn_id",
            "_record_transition",
            "_build_context_operation",
            "_record_context_snapshot_operation",
            "_persist_summary",
            "_extension_host",
            "_call_provider_operation",
            "_should_retry_with_compact",
            "_maybe_record_compact_boundary",
            "_maybe_maintain_memory",
            "_is_completion_signal",
            "_tool_presentation_snapshot",
            "_action_service",
            "_record_tool_observation",
            "_discarded_observation",
            "_interrupted_observation",
            "_is_interrupted_observation",
        )
        missing = [name for name in required if getattr(self, name) is None]
        if missing:
            raise RuntimeError("AgentLoop is missing dependencies: %s" % ", ".join(missing))

    def run(
        self,
        session: Session,
        current_mode: str,
        workflow_state: str,
        stream: bool,
        stop_event: Optional[threading.Event],
        on_text_delta: Optional[Callable[[str], None]],
        on_reasoning_delta: Optional[Callable[[str], None]],
        on_tool_start: Optional[Callable[[Action], None]],
        on_tool_finish: Optional[Callable[[Action, Observation], None]],
        on_context_result: Optional[Callable[[ContextAssemblyResult], None]],
        on_step_start: Optional[Callable[[str, int], None]],
        on_step_finish: Optional[Callable[[int, AssistantReply, str], None]],
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]],
        user_input_handler: Optional[Callable[[UserInputRequest], Optional[UserInputResponse]]],
    ) -> QueryTurnResult:
        self._ensure_configured()
        final_text = ""
        loop_guard = LoopGuard()
        turns_used = 0
        turn_index = 0
        force_compact_next_step = False
        while True:
            if stop_event is not None and stop_event.is_set():
                decision = self.continuation_policy.decide_after_step(
                    AgentLoopContinuationFacts(
                        step_index=turn_index,
                        turns_used=turns_used,
                        mode_name=current_mode,
                        workflow_state=workflow_state,
                        stop_event_set=True,
                    )
                )
                transition = self._transition_from_decision(
                    decision,
                    fallback_reason="aborted",
                    fallback_message="stop_event set",
                    turns_used=turns_used,
                )
                self._record_transition(session, transition)
                return QueryTurnResult(final_text, session, transition, turns_used)
            if self._safety_limit_reached(turn_index):
                decision = self.continuation_policy.decide_after_step(
                    AgentLoopContinuationFacts(
                        step_index=turn_index,
                        turns_used=turns_used,
                        mode_name=current_mode,
                        workflow_state=workflow_state,
                        safety_limit=self.loop_safety_limit,
                        safety_limit_reached=True,
                    )
                )
                transition = self._transition_from_decision(
                    decision,
                    fallback_reason="max_turns",
                    fallback_message="reached loop safety limit without completion signal",
                    turns_used=turns_used,
                )
                self._record_transition(session, transition)
                return QueryTurnResult(final_text, session, transition, turns_used)
            turn_index += 1
            step_index = turn_index
            step_id = "s-" + uuid.uuid4().hex[:12]
            with self._session_guard():
                self._append_transcript_event(
                    session,
                    "step_started",
                    {
                        "turn_id": session.turns[-1].turn_id if session.turns else "",
                        "step_id": step_id,
                        "step_index": step_index,
                    },
                )
                session.begin_step(step_id=step_id)
                self._emit_operation_started(
                    session,
                    "step:%s" % step_id,
                    "agent_step",
                    turn_id=session.turns[-1].turn_id if session.turns else "",
                    step_id=step_id,
                    metadata={"step_index": step_index},
                )
            if on_step_start is not None:
                on_step_start(step_id, step_index)
            force_compact = force_compact_next_step
            force_compact_next_step = False
            compact_retry_used = False
            compact_boundary_recorded = False
            operation_attempt = 0
            while True:
                operation_attempt += 1
                turn_id = self._turn_id(session)
                context_operation_id = "context:%s:%s" % (step_id, operation_attempt)
                provider_operation_id = "provider:%s:%s" % (step_id, operation_attempt)
                assembly = self._build_context_operation(
                    session,
                    current_mode,
                    workflow_state,
                    force_compact,
                    turn_id,
                    step_id,
                    context_operation_id,
                )
                with self._session_guard():
                    self._record_context_snapshot_operation(
                        session,
                        current_mode,
                        workflow_state,
                        turn_id,
                        step_id,
                        "context_snapshot:%s:%s" % (step_id, operation_attempt),
                        assembly,
                    )
                    for replacement in assembly.replacements:
                        session.record_content_replacement(dict(replacement))
                        self._append_transcript_event(
                            session,
                            "content_replacement",
                            dict(replacement),
                        )
                if on_context_result is not None:
                    on_context_result(assembly)
                self._persist_summary(session, current_mode, assembly)
                tool_schemas = self._extension_host.schemas_for_active_tools(
                    current_mode, workflow_state
                )
                try:
                    reply = self._call_provider_operation(
                        session,
                        provider_operation_id,
                        turn_id,
                        step_id,
                        current_mode,
                        workflow_state,
                        assembly.messages,
                        tool_schemas,
                        stream,
                        on_text_delta,
                        on_reasoning_delta,
                    )
                    break
                except ModelClientError as exc:
                    if compact_retry_used or not self._should_retry_with_compact(exc):
                        raise
                    compact_retry_used = True
                    force_compact = True
                    if "reactive_compact_retry" not in assembly.pipeline_steps:
                        assembly.pipeline_steps.insert(0, "reactive_compact_retry")
                    compact_boundary_recorded = (
                        self._maybe_record_compact_boundary(session, current_mode, assembly)
                        or compact_boundary_recorded
                    )
                    transition = LoopTransition(
                        reason="compact_retry",
                        message=str(exc),
                        next_mode=current_mode,
                        turns_used=turns_used,
                        metadata={
                            "source_mode": current_mode,
                            "retry_mode": "compact",
                            "error": str(exc),
                            "approx_tokens_before": assembly.approx_tokens,
                            "pipeline_steps": list(assembly.pipeline_steps),
                        },
                    )
                    self._record_transition(session, transition)
                    continue
            with self._session_guard():
                assistant_message_id = "m-" + uuid.uuid4().hex[:12]
                parent_message_id = session.last_message_id()
                self._append_message_event(
                    session,
                    {
                        "role": "assistant",
                        "content": reply.content,
                        "message_id": assistant_message_id,
                        "parent_message_id": parent_message_id,
                        "turn_id": session.turns[-1].turn_id if session.turns else "",
                        "step_id": step_id,
                        "actions": [
                            {
                                "name": action.name,
                                "arguments": dict(action.arguments),
                                "call_id": action.call_id,
                            }
                            for action in reply.actions
                        ],
                        "reasoning_content": reply.reasoning_content,
                        "finish_reason": reply.finish_reason,
                    },
                )
                session.add_assistant_reply(
                    reply,
                    message_id=assistant_message_id,
                    parent_message_id=parent_message_id,
                    turn_id=session.turns[-1].turn_id if session.turns else "",
                    step_id=step_id,
                )
                for action in reply.actions:
                    presentation = self._tool_presentation_snapshot(action.name)
                    self._append_transcript_event(
                        session,
                        "tool_call",
                        {
                            "turn_id": session.turns[-1].turn_id if session.turns else "",
                            "step_id": step_id,
                            "call_id": action.call_id,
                            "tool_name": action.name,
                            "arguments": dict(action.arguments),
                            "status": "pending",
                            "presentation": presentation.to_dict(),
                        },
                    )
                    self._emit_operation_started(
                        session,
                        "tool:%s" % action.call_id,
                        "tool_call",
                        turn_id=session.turns[-1].turn_id if session.turns else "",
                        step_id=step_id,
                        tool_call_id=action.call_id,
                        parent_operation_id="step:%s" % step_id,
                        metadata={
                            "tool_name": action.name,
                            "arguments": dict(action.arguments),
                            "presentation": presentation.to_dict(),
                        },
                    )
                    record = session._find_tool_call(action.call_id)
                    if record is not None:
                        record.presentation = presentation
            final_text = reply.content
            turns_used = step_index
            if not reply.actions and not self._has_visible_content(reply):
                decision = self.continuation_policy.decide_after_step(
                    AgentLoopContinuationFacts(
                        step_index=step_index,
                        turns_used=turns_used,
                        mode_name=current_mode,
                        workflow_state=workflow_state,
                        guard_stop_reason="provider returned empty assistant response without tool calls",
                    )
                )
                if decision.kind not in (CONTINUATION_STOP, CONTINUATION_ABORT):
                    raise RuntimeError("Unsupported continuation decision: %s" % decision.kind)
                transition = self._transition_from_decision(
                    decision,
                    fallback_reason="guard_stop",
                    fallback_message="provider returned empty assistant response without tool calls",
                    turns_used=turns_used,
                    fallback_next_mode=current_mode,
                )
                transition.metadata.setdefault("finish_reason", reply.finish_reason or "")
                transition.metadata.setdefault("empty_response", True)
                self._record_transition(session, transition)
                self._persist_summary(session, current_mode, assembly)
                if on_step_finish is not None:
                    on_step_finish(step_index, reply, transition.reason)
                return QueryTurnResult(final_text, session, transition, turns_used)
            if self._is_completion_signal(reply, session):
                decision = self.continuation_policy.decide_after_step(
                    AgentLoopContinuationFacts(
                        step_index=step_index,
                        turns_used=turns_used,
                        mode_name=current_mode,
                        workflow_state=workflow_state,
                        has_tool_calls=bool(reply.actions),
                        completion_signal=True,
                        compacted=bool(compact_boundary_recorded),
                    )
                )
                if decision.kind == CONTINUATION_CONTINUE:
                    continue
                if decision.kind == CONTINUATION_COMPACT_THEN_CONTINUE:
                    force_compact_next_step = True
                    continue
                if decision.kind not in (CONTINUATION_STOP, CONTINUATION_ABORT):
                    raise RuntimeError("Unsupported continuation decision: %s" % decision.kind)
                transition = self._transition_from_decision(
                    decision,
                    fallback_reason="completed",
                    fallback_message="agent signaled completion",
                    turns_used=turns_used,
                    fallback_next_mode=current_mode,
                )
                self._record_transition(session, transition)
                self._persist_summary(session, current_mode, assembly)
                if not compact_boundary_recorded:
                    self._maybe_record_compact_boundary(session, current_mode, assembly)
                self._maybe_maintain_memory(True)
                if on_step_finish is not None:
                    on_step_finish(step_index, reply, transition.reason)
                return QueryTurnResult(final_text, session, transition, turns_used)
            executor = StreamingToolExecutor(
                lambda action: self._action_service.execute_parallel_tool_action(
                    session,
                    action,
                    current_mode,
                    workflow_state,
                    stop_event,
                ),
                self.max_parallel_tools,
                cancel_event=stop_event,
            )
            discard_remaining_batches = False
            for batch in partition_tool_actions(
                reply.actions,
                self.tool_capabilities,
            ):
                if discard_remaining_batches:
                    for action in batch.actions:
                        observation = self._discarded_observation(action.name)
                        self._record_tool_observation(
                            session,
                            action,
                            observation,
                            current_mode,
                            assembly,
                            step_id,
                            on_tool_finish,
                        )
                        loop_guard.record(action, observation)
                    continue
                if not batch.parallel:
                    for action in batch.actions:
                        if on_tool_start is not None:
                            on_tool_start(action)
                        self._emit_lifecycle_event(
                            session,
                            "tool_use",
                            {
                                "role": "tool_use",
                                "tool_name": action.name,
                                "call_id": action.call_id,
                                "arguments": dict(action.arguments),
                                "message_id": "m-tool-use-" + uuid.uuid4().hex[:12],
                                "parent_message_id": session.last_message_id(),
                                "turn_id": session.turns[-1].turn_id if session.turns else "",
                                "step_id": (
                                    session.current_step().step_id if session.current_step() else ""
                                ),
                                "status": "started",
                            },
                        )
                        interrupted = bool(stop_event is not None and stop_event.is_set())
                        suspended = None
                        if interrupted:
                            observation = self._interrupted_observation(action.name)
                        else:
                            observation, current_mode, suspended = (
                                self._action_service.execute_action(
                                    session,
                                    action,
                                    current_mode,
                                    workflow_state,
                                    permission_handler,
                                    user_input_handler,
                                    stop_event=stop_event,
                                )
                            )
                            if suspended is not None:
                                self._persist_summary(session, current_mode, assembly)
                                if on_step_finish is not None:
                                    on_step_finish(step_index, reply, suspended.transition.reason)
                                return suspended
                            if (
                                stop_event is not None
                                and stop_event.is_set()
                                and not self._is_interrupted_observation(observation)
                            ):
                                interrupted = True
                                observation = self._interrupted_observation(action.name)
                        self._emit_lifecycle_event(
                            session,
                            "command_execution",
                            {
                                "role": "command_execution",
                                "call_id": action.call_id,
                                "tool_name": action.name,
                                "output_chunk": str(observation.data) if observation.data else "",
                                "message_id": "m-cmd-" + uuid.uuid4().hex[:12],
                                "parent_message_id": session.last_message_id(),
                                "turn_id": session.turns[-1].turn_id if session.turns else "",
                                "step_id": (
                                    session.current_step().step_id if session.current_step() else ""
                                ),
                                "status": "updated",
                            },
                        )
                        self._record_tool_observation(
                            session,
                            action,
                            observation,
                            current_mode,
                            assembly,
                            step_id,
                            on_tool_finish,
                        )
                        loop_guard.record(action, observation)
                        if interrupted:
                            transition = LoopTransition(
                                reason="aborted",
                                message="tool execution interrupted",
                                turns_used=turns_used,
                            )
                            self._record_transition(session, transition)
                            if on_step_finish is not None:
                                on_step_finish(step_index, reply, "aborted")
                            return QueryTurnResult(final_text, session, transition, turns_used)
                        if loop_guard.should_block(action) or loop_guard.should_stop():
                            transition = LoopTransition(
                                reason="guard_stop",
                                message=loop_guard.stop_reason(),
                                turns_used=turns_used,
                            )
                            self._record_transition(session, transition)
                            if on_step_finish is not None:
                                on_step_finish(step_index, reply, "guard_stop")
                            return QueryTurnResult(final_text, session, transition, turns_used)
                    continue
                batch_interrupted = False
                batch_discarded = False
                for update in executor.run_batch(batch):
                    if update.phase == "start":
                        if on_tool_start is not None:
                            on_tool_start(update.action)
                        self._emit_lifecycle_event(
                            session,
                            "tool_use",
                            {
                                "role": "tool_use",
                                "tool_name": update.action.name,
                                "call_id": update.action.call_id,
                                "arguments": dict(update.action.arguments),
                                "message_id": "m-tool-use-" + uuid.uuid4().hex[:12],
                                "parent_message_id": session.last_message_id(),
                                "turn_id": session.turns[-1].turn_id if session.turns else "",
                                "step_id": (
                                    session.current_step().step_id if session.current_step() else ""
                                ),
                                "status": "started",
                            },
                        )
                        if stop_event is not None and stop_event.is_set():
                            batch_interrupted = True
                            executor.discard()
                        continue
                    suspended = None
                    if batch_interrupted or (stop_event is not None and stop_event.is_set()):
                        batch_interrupted = True
                        if (
                            update.observation is not None
                            and isinstance(update.observation.data, dict)
                            and update.observation.data.get("error_kind") == "discarded"
                        ):
                            observation = update.observation
                        else:
                            observation = self._interrupted_observation(update.action.name)
                    else:
                        observation, current_mode, suspended = self._action_service.execute_action(
                            session,
                            update.action,
                            current_mode,
                            workflow_state,
                            permission_handler,
                            user_input_handler,
                            update.observation,
                            stop_event=stop_event,
                        )
                        if suspended is not None:
                            self._persist_summary(session, current_mode, assembly)
                            if on_step_finish is not None:
                                on_step_finish(step_index, reply, suspended.transition.reason)
                            return suspended
                        if (
                            stop_event is not None
                            and stop_event.is_set()
                            and not self._is_interrupted_observation(observation)
                        ):
                            batch_interrupted = True
                            executor.discard()
                            observation = self._interrupted_observation(update.action.name)
                    self._emit_lifecycle_event(
                        session,
                        "command_execution",
                        {
                            "role": "command_execution",
                            "call_id": update.action.call_id,
                            "tool_name": update.action.name,
                            "output_chunk": str(observation.data) if observation.data else "",
                            "message_id": "m-cmd-" + uuid.uuid4().hex[:12],
                            "parent_message_id": session.last_message_id(),
                            "turn_id": session.turns[-1].turn_id if session.turns else "",
                            "step_id": (
                                session.current_step().step_id if session.current_step() else ""
                            ),
                            "status": "updated",
                        },
                    )
                    if (
                        isinstance(observation.data, dict)
                        and observation.data.get("error_kind") == "discarded"
                    ):
                        batch_discarded = True
                    self._record_tool_observation(
                        session,
                        update.action,
                        observation,
                        current_mode,
                        assembly,
                        step_id,
                        on_tool_finish,
                    )
                    loop_guard.record(update.action, observation)
                    if batch_interrupted:
                        continue
                    # For parallel batches, only check should_stop (consecutive failures)
                    # during the batch. should_block (repeated tool calls) is checked
                    # at batch boundaries to avoid blocking legitimate parallel usage.
                    if loop_guard.should_stop():
                        transition = LoopTransition(
                            reason="guard_stop",
                            message=loop_guard.stop_reason(),
                            turns_used=turns_used,
                        )
                        self._record_transition(session, transition)
                        if on_step_finish is not None:
                            on_step_finish(step_index, reply, "guard_stop")
                        return QueryTurnResult(final_text, session, transition, turns_used)
                if batch_interrupted:
                    transition = LoopTransition(
                        reason="aborted",
                        message="tool execution interrupted",
                        turns_used=turns_used,
                    )
                    self._record_transition(session, transition)
                    if on_step_finish is not None:
                        on_step_finish(step_index, reply, "aborted")
                    return QueryTurnResult(final_text, session, transition, turns_used)
                if batch_discarded:
                    discard_remaining_batches = True
            if on_step_finish is not None:
                on_step_finish(step_index, reply, "tool_calls")
            self._emit_step_finished(
                session,
                self._turn_id(session),
                step_id,
                "tool_calls",
                turns_used=turns_used,
            )
            decision = self.continuation_policy.decide_after_step(
                AgentLoopContinuationFacts(
                    step_index=step_index,
                    turns_used=turns_used,
                    mode_name=current_mode,
                    workflow_state=workflow_state,
                    has_tool_calls=bool(reply.actions),
                    completion_signal=False,
                    compacted=bool(compact_boundary_recorded),
                )
            )
            if decision.kind == CONTINUATION_CONTINUE:
                continue
            if decision.kind == CONTINUATION_COMPACT_THEN_CONTINUE:
                force_compact_next_step = True
                continue
            if decision.kind in (CONTINUATION_STOP, CONTINUATION_ABORT):
                transition = self._transition_from_decision(
                    decision,
                    fallback_reason=decision.reason or "aborted",
                    fallback_message=decision.message or "",
                    turns_used=turns_used,
                )
                self._record_transition(session, transition)
                return QueryTurnResult(final_text, session, transition, turns_used)
            raise RuntimeError("Unsupported continuation decision: %s" % decision.kind)
