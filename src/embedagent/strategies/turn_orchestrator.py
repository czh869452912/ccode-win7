"""Turn orchestrator: single turn execution from prompt to observations.

Extracted from QueryEngine to separate turn execution concerns.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from embedagent.guard import LoopGuard
from embedagent.llm import ModelClientError
from embedagent.permissions import PermissionPolicy, PermissionRequest
from embedagent.session import (
    Action,
    LoopTransition,
    Observation,
    PendingInteraction,
    QueryTurnResult,
)
from embedagent.strategies.execution_tracer import ExecutionTracer, TraceEventType
from embedagent.tool_execution import StreamingToolExecutor, partition_tool_actions
from embedagent.tools._base import ToolError

_LOG = logging.getLogger(__name__)


class TurnOrchestrator(object):
    """Orchestrates a single turn: prompt -> LLM -> tool actions -> observations."""

    def __init__(
        self,
        llm_wrapper: Any,
        tools: Any,
        permission_policy: Optional[PermissionPolicy] = None,
        max_parallel_tools: int = 3,
        streaming_executor: Optional[Any] = None,
        tracer: Optional[ExecutionTracer] = None,
    ) -> None:
        self.llm_wrapper = llm_wrapper
        self.tools = tools
        self.permission_policy = permission_policy or PermissionPolicy(auto_approve_all=True)
        self.max_parallel_tools = max(1, int(max_parallel_tools or 1))
        self.streaming_executor = streaming_executor
        self.tracer = tracer

    def execute_turn(
        self,
        session: Any,
        messages: List[Dict[str, Any]],
        tool_schemas: List[Dict[str, Any]],
        current_mode: str = "build",
        workflow_state: str = "chat",
        stream: bool = False,
        stop_event: Optional[Any] = None,
        on_text_delta: Optional[Callable[[str], None]] = None,
        on_reasoning_delta: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[Action], None]] = None,
        on_tool_finish: Optional[Callable[[Action, Observation], None]] = None,
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]] = None,
        user_input_handler: Optional[Any] = None,
        step_id: str = "",
    ) -> QueryTurnResult:
        """Execute one turn: call LLM, process reply, execute tools."""
        turn_id = getattr(session, "turn_id", "") or ""
        session_id = getattr(session, "session_id", "") or ""

        # 1. Call LLM
        if self.tracer is not None:
            self.tracer.record(
                TraceEventType.LLM_CALL_START,
                session_id,
                turn_id,
                step_id=step_id,
                data={"message_count": len(messages), "tool_count": len(tool_schemas)},
            )

        try:
            reply = self.llm_wrapper.call_with_retry(
                messages=messages,
                tools=tool_schemas,
                stream=stream,
                on_text_delta=on_text_delta,
                on_reasoning_delta=on_reasoning_delta,
            )
            if self.tracer is not None:
                self.tracer.record(
                    TraceEventType.LLM_CALL_END,
                    session_id,
                    turn_id,
                    step_id=step_id,
                    data={"action_count": len(reply.actions), "finish_reason": reply.finish_reason},
                )
        except ModelClientError as exc:
            if self.tracer is not None:
                self.tracer.record(
                    TraceEventType.ERROR,
                    session_id,
                    turn_id,
                    step_id=step_id,
                    data={"error_type": "ModelClientError", "error_message": str(exc)},
                )
            transition = LoopTransition(
                reason="error",
                message=str(exc),
                next_mode=current_mode,
            )
            return QueryTurnResult("", session, transition)

        # 2. No tool actions -> completed
        if not reply.actions:
            transition = LoopTransition(
                reason="completed",
                message="assistant finished",
                next_mode=current_mode,
            )
            return QueryTurnResult(reply.content, session, transition)

        # 3. Execute tools
        loop_guard = LoopGuard()
        discard_remaining_batches = False

        for batch in partition_tool_actions(reply.actions, self.tools.tool_capabilities):
            if discard_remaining_batches:
                for action in batch.actions:
                    observation = self._discarded_observation(action.name)
                    if on_tool_finish is not None:
                        on_tool_finish(action, observation)
                    loop_guard.record(action, observation)
                continue

            if not batch.parallel:
                for action in batch.actions:
                    if on_tool_start is not None:
                        on_tool_start(action)

                    if stop_event is not None and stop_event.is_set():
                        observation = self._interrupted_observation(action.name)
                        transition = LoopTransition(
                            reason="aborted",
                            message="tool execution interrupted",
                            next_mode=current_mode,
                        )
                        if on_tool_finish is not None:
                            on_tool_finish(action, observation)
                        return QueryTurnResult(reply.content, session, transition)

                    observation, current_mode, suspended = self._execute_action(
                        session,
                        action,
                        current_mode,
                        workflow_state,
                        permission_handler,
                        user_input_handler,
                        stop_event=stop_event,
                    )

                    if suspended is not None:
                        return suspended

                    if on_tool_finish is not None:
                        on_tool_finish(action, observation)

                    loop_guard.record(action, observation)

                    if loop_guard.should_block(action) or loop_guard.should_stop():
                        transition = LoopTransition(
                            reason="guard_stop",
                            message=loop_guard.stop_reason(),
                            next_mode=current_mode,
                        )
                        return QueryTurnResult(reply.content, session, transition)

                continue

            # Parallel batch execution
            def _execute_tool(action):
                try:
                    return self.tools.execute_with_interrupt(
                        action.name, action.arguments, stop_event
                    )
                except ToolError as exc:
                    return self._failure_observation(
                        action.name,
                        str(exc),
                        "tool_error",
                        False,
                        "tool_execution",
                    )

            executor = StreamingToolExecutor(
                _execute_tool,
                self.max_parallel_tools,
                cancel_event=stop_event,
            )
            batch_interrupted = False
            batch_discarded = False

            for update in executor.run_batch(batch):
                if update.phase == "start":
                    if on_tool_start is not None:
                        on_tool_start(update.action)
                    if stop_event is not None and stop_event.is_set():
                        batch_interrupted = True
                        executor.discard()
                    continue

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
                    observation, current_mode, suspended = self._execute_action(
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
                        return suspended
                    if (
                        stop_event is not None
                        and stop_event.is_set()
                        and not self._is_interrupted_observation(observation)
                    ):
                        batch_interrupted = True
                        executor.discard()
                        observation = self._interrupted_observation(update.action.name)

                if (
                    isinstance(observation.data, dict)
                    and observation.data.get("error_kind") == "discarded"
                ):
                    batch_discarded = True

                if on_tool_finish is not None:
                    on_tool_finish(update.action, observation)

                loop_guard.record(update.action, observation)

                if batch_interrupted:
                    continue

                if loop_guard.should_block(update.action) or loop_guard.should_stop():
                    transition = LoopTransition(
                        reason="guard_stop",
                        message=loop_guard.stop_reason(),
                        next_mode=current_mode,
                    )
                    return QueryTurnResult(reply.content, session, transition)

            if batch_interrupted:
                transition = LoopTransition(
                    reason="aborted",
                    message="tool execution interrupted",
                    next_mode=current_mode,
                )
                return QueryTurnResult(reply.content, session, transition)

            if batch_discarded:
                discard_remaining_batches = True

        transition = LoopTransition(
            reason="tool_calls",
            message="tools executed",
            next_mode=current_mode,
        )
        return QueryTurnResult(reply.content, session, transition)

    def _execute_action(
        self,
        session: Any,
        action: Action,
        current_mode: str,
        workflow_state: str,
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]],
        user_input_handler: Optional[Any],
        precomputed_observation: Optional[Observation] = None,
        stop_event: Optional[Any] = None,
    ) -> Tuple[Observation, str, Optional[QueryTurnResult]]:
        """Execute a single tool action with permission handling."""
        turn_id = getattr(session, "turn_id", "") or ""
        session_id = getattr(session, "session_id", "") or ""

        if precomputed_observation is not None:
            return precomputed_observation, current_mode, None

        allowed = set(self.tools.allowed_tool_names(current_mode, workflow_state=workflow_state))
        if action.name not in allowed and action.name not in ("ask_user", "propose_mode_switch"):
            return (
                self._failure_observation(
                    action.name,
                    "current mode %s does not allow tool %s" % (current_mode, action.name),
                    "mode_tool_blocked",
                    False,
                    current_mode,
                ),
                current_mode,
                None,
            )

        if action.name == "task_status":
            summary = ""
            phase = ""
            discipline = ""
            task_items = []
            if not session.task_graph.is_empty():
                mode_context = self.tools.describe_mode(current_mode, workflow_state=workflow_state)
                if mode_context is not None:
                    summary = str(getattr(mode_context, "task_summary", "") or "")
                    phase = str(getattr(mode_context, "current_phase", "") or "")
                    discipline = str(getattr(mode_context, "discipline_label", "") or "")
                    task_items = list(getattr(mode_context, "task_items", []) or [])
            if not summary:
                summary = "no active tasks"
            observation = Observation(
                tool_name="task_status",
                success=True,
                error=None,
                data={
                    "summary": summary,
                    "preview": [line for line in summary.splitlines() if line],
                    "returned_count": len([line for line in summary.splitlines() if line]),
                    "total_count": len([line for line in summary.splitlines() if line]),
                    "has_more": False,
                    "next_offset": 0,
                    "result_ref": "",
                    "current_mode": current_mode,
                    "current_phase": phase,
                    "discipline_profile": discipline,
                    "tasks": task_items,
                },
            )
            return observation, current_mode, None

        # Permission check for non-special tools
        if action.name not in ("ask_user", "propose_mode_switch", "task_status"):
            if self.tracer is not None:
                self.tracer.record(
                    TraceEventType.PERMISSION_REQUEST,
                    session_id,
                    turn_id,
                    data={"tool_name": action.name},
                )
            decision = self.permission_policy.evaluate(action)
            if self.tracer is not None:
                self.tracer.record(
                    TraceEventType.PERMISSION_DECISION,
                    session_id,
                    turn_id,
                    data={"tool_name": action.name, "decision": decision.outcome},
                )
            if decision.outcome == "deny":
                return (
                    self._failure_observation(
                        action.name,
                        decision.error or "permission denied",
                        "permission_denied",
                        False,
                        "permission_policy",
                    ),
                    current_mode,
                    None,
                )
            if decision.request is not None:
                approved = (
                    permission_handler(decision.request) if permission_handler is not None else None
                )
                if approved is None:
                    pending = PendingInteraction(
                        kind="permission",
                        tool_name=action.name,
                    )
                    transition = LoopTransition(
                        reason="permission_wait",
                        message=decision.request.reason,
                        pending_interaction=pending,
                        next_mode=current_mode,
                    )
                    return (
                        self._failure_observation(
                            action.name,
                            "waiting permission",
                            "pending_interaction",
                            False,
                            "permission",
                            extra_data={"pending": True},
                        ),
                        current_mode,
                        QueryTurnResult("", session, transition, pending_interaction=pending),
                    )
                if not approved:
                    return (
                        self._failure_observation(
                            action.name,
                            "operation not approved",
                            "permission_denied",
                            False,
                            "user_confirmation",
                            extra_data={"permission_required": True, "permission_decision": "deny"},
                        ),
                        current_mode,
                        None,
                    )

        # Execute the tool
        if self.tracer is not None:
            self.tracer.record(
                TraceEventType.TOOL_EXECUTION_START,
                session_id,
                turn_id,
                data={"tool_name": action.name},
            )
        try:
            observation = self.tools.execute_with_interrupt(
                action.name, action.arguments, stop_event
            )
            if self.tracer is not None:
                self.tracer.record(
                    TraceEventType.TOOL_EXECUTION_END,
                    session_id,
                    turn_id,
                    data={"tool_name": action.name, "success": observation.success},
                )
        except ToolError as exc:
            if self.tracer is not None:
                self.tracer.record(
                    TraceEventType.ERROR,
                    session_id,
                    turn_id,
                    data={
                        "tool_name": action.name,
                        "error_type": "ToolError",
                        "error_message": str(exc),
                    },
                )
            observation = self._failure_observation(
                action.name,
                str(exc),
                "tool_error",
                False,
                "tool_execution",
            )

        return observation, current_mode, None

    def _interrupted_observation(self, tool_name: str) -> Observation:
        return Observation(
            tool_name=tool_name,
            success=False,
            error="tool execution interrupted",
            data={
                "error_kind": "interrupted",
                "retryable": False,
                "blocked_by": "user_cancelled",
                "synthetic": True,
            },
        )

    def _discarded_observation(self, tool_name: str) -> Observation:
        return Observation(
            tool_name=tool_name,
            success=False,
            error="tool execution discarded",
            data={
                "error_kind": "discarded",
                "retryable": False,
                "synthetic": True,
            },
        )

    def _is_interrupted_observation(self, observation: Observation) -> bool:
        return bool(
            isinstance(observation.data, dict)
            and str(observation.data.get("error_kind") or "") == "interrupted"
        )

    def _failure_observation(
        self,
        tool_name: str,
        error: str,
        error_kind: str,
        retryable: bool,
        blocked_by: str,
        suggested_next_step: str = "",
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Observation:
        data = {
            "error_kind": error_kind,
            "retryable": retryable,
            "blocked_by": blocked_by,
            "suggested_next_step": suggested_next_step or "",
        }
        if extra_data:
            data.update(extra_data)
        return Observation(tool_name, False, error, data)
