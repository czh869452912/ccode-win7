from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Optional, Tuple

from embedagent_core.agent_effects import (
    AssembleContextEffect,
    EffectFailed,
    ExecutePreparedToolBatchEffect,
    PrepareToolBatchEffect,
    ProviderCompleted,
    RequestProviderEffect,
    ToolBatchCompleted,
    ToolBatchPrepared,
)
from embedagent_core.agent_kernel import AgentKernel, KernelStep
from embedagent_core.agent_loop_continuation import AgentLoopContinuationPolicy
from embedagent_core.agent_tool_action_service import AgentToolActionService
from embedagent_core.guard import ProgressGuard
from embedagent_core.provider_step_service import ProviderObserver, ProviderStepService
from embedagent_core.session import (
    Action,
    AssistantReply,
    LoopTransition,
    Observation,
    QueryTurnResult,
    Session,
)
from embedagent_core.session_journal import SessionJournal
from embedagent_core.session_reducer import SessionReducerContext

_LOG = logging.getLogger(__name__)
_OBSERVER_ERRORS = (
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
)


class AgentLoop(object):
    """Commit, execute, and resume the closed Agent Core effect machine."""

    def __init__(
        self,
        kernel: AgentKernel,
        journal: SessionJournal,
        provider_steps: ProviderStepService,
        tool_actions: AgentToolActionService,
        continuation_policy: AgentLoopContinuationPolicy,
    ) -> None:
        self._kernel = kernel
        self._journal = journal
        self._provider_steps = provider_steps
        self._tool_actions = tool_actions
        self._continuation_policy = continuation_policy

    @property
    def continuation_policy(self) -> AgentLoopContinuationPolicy:
        return self._continuation_policy

    def run(
        self,
        session: Session,
        reduction_context: SessionReducerContext,
        turn_id: str,
        current_mode: str,
        workflow_state: str,
        source: str = "user",
        stream: bool = False,
        observer: Optional[Any] = None,
        cancel: Optional[Any] = None,
        max_turns: Optional[int] = None,
        max_parallel_tools: int = 3,
    ) -> QueryTurnResult:
        step = self._kernel.start(
            turn_id,
            current_mode,
            workflow_state,
            source,
            stream=stream,
            step_index=self._next_step_index(session, turn_id),
        )
        final_text = ""
        observer_enabled = observer is not None
        progress_guard = ProgressGuard()
        pending_context = None
        pending_tool_notifications = ()  # type: Tuple[Tuple[Action, Observation], ...]
        pending_step_finish = None
        last_reply = AssistantReply("")
        on_context_result = self._observer_callback(observer, "on_context_result")
        on_tool_finish = self._observer_callback(observer, "on_tool_finish")
        on_step_finish = self._observer_callback(observer, "on_step_finish")
        on_step_start = self._observer_callback(observer, "on_step_start")

        while True:
            committed_events = self._commit(step, session, reduction_context)
            if observer_enabled:
                observer_enabled = self._publish_committed(observer, committed_events)
            if pending_context is not None and on_context_result is not None:
                on_context_result(pending_context)
                pending_context = None
            if pending_tool_notifications and on_tool_finish is not None:
                for action, observation in pending_tool_notifications:
                    on_tool_finish(action, observation)
                pending_tool_notifications = ()
            if pending_step_finish is not None and on_step_finish is not None:
                on_step_finish(*pending_step_finish)
                pending_step_finish = None
            self._notify_step_starts(committed_events, on_step_start)
            self._finalize(step.post_commit_tokens)

            if step.outcome is not None:
                pending = session.pending_interaction or step.outcome.pending_interaction
                transition = self._transition_with_pending(step.outcome, pending)
                if on_step_finish is not None and pending_step_finish is None:
                    on_step_finish(step.cursor.step_index, last_reply, transition.reason)
                return QueryTurnResult(
                    final_text,
                    session,
                    transition,
                    turns_used=transition.turns_used,
                    pending_interaction=pending,
                )
            if step.effect is None:
                raise RuntimeError("agent kernel produced neither effect nor outcome")

            if self._is_cancelled(cancel):
                effect_result = EffectFailed(
                    step.effect.effect_id,
                    "cancelled",
                    "stop_event set",
                    retryable=False,
                )
            else:
                effect_result = self._execute_effect(
                    step.effect,
                    session,
                    observer,
                    cancel,
                    max_parallel_tools,
                )

            if hasattr(effect_result, "assembly"):
                pending_context = effect_result.assembly
            if isinstance(effect_result, ProviderCompleted):
                last_reply = effect_result.reply
                final_text = effect_result.reply.content
            tool_pairs = self._tool_result_pairs(step.effect, effect_result)
            if tool_pairs:
                pending_tool_notifications = tool_pairs
                for action, observation in pending_tool_notifications:
                    progress_guard.record(action, observation)
                cancelled = isinstance(
                    effect_result,
                    ToolBatchCompleted,
                ) and self._tool_result_is_cancelled(effect_result, cancel)
                failure_kind = ""
                failure_message = ""
                failure_metadata = {}
                if cancelled:
                    failure_kind = "cancelled"
                    failure_message = "tool execution interrupted"
                elif self._guard_should_stop(progress_guard, pending_tool_notifications):
                    failure_kind = "guard_stop"
                    failure_message = progress_guard.stop_reason()
                elif self._safety_limit_reached_after_tools(step, max_turns):
                    limit = int(max_turns or 0)
                    failure_kind = "safety_limit"
                    failure_message = "reached loop safety limit without completion signal"
                    failure_metadata = {
                        "loop_safety_limit": limit,
                        "turns_used": limit,
                    }
                if failure_kind:
                    effect_result = EffectFailed(
                        effect_result.effect_id,
                        failure_kind,
                        failure_message,
                        retryable=False,
                        events=effect_result.events,
                        commit_tokens=effect_result.commit_tokens,
                        metadata=failure_metadata,
                    )
                else:
                    pending_step_finish = (
                        step.cursor.step_index,
                        last_reply,
                        "tool_calls",
                    )

            step = self._kernel.accept(step.cursor, effect_result)

    def _commit(
        self,
        step: KernelStep,
        session: Session,
        reduction_context: SessionReducerContext,
    ) -> Tuple[dict, ...]:
        if not step.events:
            return ()
        committed = self._journal.commit(session, reduction_context, step.events)
        return tuple(committed.events)

    def _publish_committed(self, observer: Any, events: Tuple[dict, ...]) -> bool:
        callback = getattr(observer, "on_event", None)
        if not callable(callback):
            return False
        for event in events:
            try:
                callback(
                    str(event.get("type") or ""),
                    dict(event.get("payload") or {}),
                )
            except _OBSERVER_ERRORS as exc:
                _LOG.warning("agent event observer disabled after failure: %s", exc)
                return False
        return True

    def _notify_step_starts(
        self,
        events: Tuple[dict, ...],
        callback: Optional[Any],
    ) -> None:
        if callback is None:
            return
        for event in events:
            if str(event.get("type") or "") != "step_started":
                continue
            payload = dict(event.get("payload") or {})
            callback(
                str(payload.get("step_id") or ""),
                int(payload.get("step_index") or 0),
            )

    def _finalize(self, commit_tokens: Tuple[Any, ...]) -> None:
        if not commit_tokens:
            return
        try:
            self._tool_actions.finalize(tuple(commit_tokens))
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            _LOG.warning("tool result projection finalization failed: %s", exc)

    def _execute_effect(
        self,
        effect: Any,
        session: Session,
        observer: Optional[Any],
        cancel: Optional[Any],
        max_parallel_tools: int,
    ):
        if isinstance(effect, AssembleContextEffect):
            return self._provider_steps.assemble_context(effect, session)
        if isinstance(effect, RequestProviderEffect):
            return self._provider_steps.request_provider(
                effect,
                ProviderObserver(
                    self._observer_callback(observer, "on_text_delta"),
                    self._observer_callback(observer, "on_reasoning_delta"),
                ),
            )
        if isinstance(effect, PrepareToolBatchEffect):
            return self._tool_actions.prepare(
                effect,
                session,
                permission_handler=self._observer_callback(
                    observer,
                    "on_permission_request",
                ),
                user_input_handler=self._observer_callback(
                    observer,
                    "on_user_input_request",
                ),
            )
        if isinstance(effect, ExecutePreparedToolBatchEffect):
            return self._tool_actions.execute_prepared(
                effect,
                session,
                stop_event=cancel,
                on_action_start=self._observer_callback(observer, "on_tool_start"),
                max_parallel_tools=max_parallel_tools,
            )
        raise TypeError("unsupported agent effect")

    def _observer_callback(self, observer: Optional[Any], name: str):
        callback = getattr(observer, name, None) if observer is not None else None
        return callback if callable(callback) else None

    def _is_cancelled(self, cancel: Optional[Any]) -> bool:
        is_set = getattr(cancel, "is_set", None)
        return bool(callable(is_set) and is_set())

    def _safety_limit_reached_after_tools(
        self,
        step: KernelStep,
        max_turns: Optional[int],
    ) -> bool:
        if max_turns is None:
            return False
        limit = int(max_turns or 0)
        return limit > 0 and step.cursor.step_index >= limit

    def _tool_result_pairs(
        self,
        effect: Any,
        result: Any,
    ) -> Tuple[Tuple[Action, Observation], ...]:
        if isinstance(result, ToolBatchPrepared):
            if result.invocations:
                return ()
            ordered_immediate = sorted(
                result.immediate_results,
                key=lambda item: item.source_index,
            )
            return tuple(
                (
                    item.original_action.to_action(),
                    item.observation,
                )
                for item in ordered_immediate
            )
        if not isinstance(result, ToolBatchCompleted) or not isinstance(
            effect,
            ExecutePreparedToolBatchEffect,
        ):
            return ()
        sources = [
            (item.source_index, item.original_action.to_action())
            for item in effect.immediate_results
        ]
        sources.extend(
            (item.source_index, item.original_action.to_action()) for item in effect.invocations
        )
        ordered_actions = [item[1] for item in sorted(sources, key=lambda item: item[0])]
        return tuple(zip(ordered_actions, result.observations))

    def _tool_result_is_cancelled(
        self,
        result: ToolBatchCompleted,
        cancel: Optional[Any],
    ) -> bool:
        if self._is_cancelled(cancel):
            return True
        for observation in result.observations:
            if (
                isinstance(observation.data, dict)
                and str(observation.data.get("error_kind") or "") == "interrupted"
            ):
                return True
        return False

    def _guard_should_stop(
        self,
        guard: ProgressGuard,
        pairs: Tuple[Tuple[Action, Observation], ...],
    ) -> bool:
        if guard.should_stop():
            return True
        return any(guard.should_block(action) for action, observation in pairs)

    def _transition_with_pending(
        self,
        transition: LoopTransition,
        pending: Any,
    ) -> LoopTransition:
        if transition.pending_interaction is pending:
            return transition
        return replace(transition, pending_interaction=pending)

    def _next_step_index(self, session: Session, turn_id: str) -> int:
        if not session.turns:
            return 1
        turn = session.turns[-1]
        if str(turn.turn_id or "") != str(turn_id or ""):
            return 1
        return len(turn.steps) + 1
