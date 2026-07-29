from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Optional

from embedagent_core.api import (
    AgentInput,
    AgentObserver,
    AgentResult,
    AgentSessionView,
    CancelToken,
    InteractionReply,
    RuntimeDefinition,
    UserTurn,
)
from embedagent_core.ports import StrictSessionRestorePolicy
from embedagent_core.session import (
    Action,
    AssistantReply,
    ContextAssemblyResult,
    Observation,
    QueryTurnResult,
    Session,
)
from embedagent_core.session_journal import SessionJournal
from embedagent_core.session_reducer import SessionReducerContext


@dataclass(frozen=True)
class AgentRequest:
    session_id: str
    input: AgentInput


@dataclass(frozen=True)
class SessionTransactionState:
    session: Session
    current_mode: str
    reduction_context: SessionReducerContext


class SessionRecoveryRequired(RuntimeError):
    def __init__(self, session_id: str, stop_reason: str) -> None:
        self.session_id = str(session_id or "")
        self.stop_reason = str(stop_reason or "incomplete_transcript")
        super(SessionRecoveryRequired, self).__init__(
            "session recovery required for %s: %s" % (self.session_id, self.stop_reason)
        )


class SessionTransaction(object):
    """Own one leased restore-dispatch-project transaction for a durable session."""

    def __init__(
        self,
        session_log: Any,
        journal: SessionJournal,
        loop: Any,
        definition: RuntimeDefinition,
        projection: Any,
        dispatcher: Any,
        event_committer: Any,
        restore_policy: Optional[Any] = None,
    ) -> None:
        self._session_log = session_log
        self._journal = journal
        self._loop = loop
        self._definition = definition
        self._projection = projection
        self._dispatcher = dispatcher
        self._event_committer = event_committer
        self._restore_policy = restore_policy or StrictSessionRestorePolicy()
        self._lease_state = threading.local()

    def submit(
        self,
        request: AgentRequest,
        observer: Optional[AgentObserver] = None,
        cancel: Optional[CancelToken] = None,
    ) -> AgentResult:
        session_id = str(request.session_id or "").strip()
        with self._lease(session_id):
            state = self._restore_or_create(session_id)
            with self._event_committer.bind(state.reduction_context):
                result, initial_mode = self._dispatch(
                    state,
                    request.input,
                    observer,
                    cancel,
                )
                return self._project_result(result, initial_mode)

    def initialize_host(
        self,
        session_id: str,
        session: Session,
        current_mode: str,
        workflow_state: str,
    ) -> str:
        return self._host_dispatch(
            session_id,
            session,
            current_mode,
            self._dispatcher.initialize_session,
            session,
            current_mode,
            workflow_state=workflow_state,
        )

    def apply_host_mode(
        self,
        session_id: str,
        session: Session,
        mode: str,
        workflow_state: str,
    ) -> str:
        return self._host_dispatch(
            session_id,
            session,
            mode,
            self._dispatcher.apply_mode,
            session,
            mode,
            workflow_state=workflow_state,
        )

    def record_host_command(self, session_id: str, session: Session, **kwargs: Any) -> None:
        self._host_dispatch(
            session_id,
            session,
            "",
            self._dispatcher.record_command_result,
            session,
            **kwargs,
        )

    def submit_host_command(self, session_id: str, **kwargs: Any) -> Any:
        session = kwargs.get("session")
        mode = str(kwargs.get("initial_mode") or "")
        return self._host_dispatch(
            session_id,
            session,
            mode,
            self._dispatcher.submit_command_turn,
            **kwargs,
        )

    def resume_host_command(self, session_id: str, **kwargs: Any) -> Any:
        session = kwargs.get("session")
        mode = str(kwargs.get("initial_mode") or "")
        return self._host_dispatch(
            session_id,
            session,
            mode,
            self._dispatcher.resume_interaction,
            **kwargs,
        )

    @contextmanager
    def _lease(self, session_id: str) -> Iterator[None]:
        depths = getattr(self._lease_state, "depths", None)
        if depths is None:
            depths = {}
            self._lease_state.depths = depths
        depth = int(depths.get(session_id, 0) or 0)
        if depth:
            depths[session_id] = depth + 1
            try:
                yield
            finally:
                depths[session_id] -= 1
            return
        with self._session_log.acquire_lease(session_id):
            depths[session_id] = 1
            try:
                yield
            finally:
                depths.pop(session_id, None)

    def _restore_or_create(self, session_id: str) -> SessionTransactionState:
        if not self._session_log.transcript_exists(session_id):
            current_mode = self._definition.default_mode
            return SessionTransactionState(
                Session(session_id=session_id),
                current_mode,
                SessionReducerContext(current_mode=current_mode),
            )
        restored = self._journal.restore(session_id, self._restore_policy)
        if restored.stop_reason or restored.consumed_event_count != restored.transcript_event_count:
            raise SessionRecoveryRequired(session_id, restored.stop_reason)
        if self._has_incomplete_side_effect(restored.operation_state, restored.session):
            raise SessionRecoveryRequired(session_id, "incomplete_side_effect")
        return SessionTransactionState(
            restored.session,
            restored.current_mode,
            restored.reduction_context,
        )

    def _has_incomplete_side_effect(self, operation_state: Any, session: Session) -> bool:
        for operation in operation_state.operations.values():
            if self._is_pending_interaction_operation(operation, session):
                continue
            if (
                operation.kind == "tool_call"
                and operation.status == "interrupted"
                and operation.interrupted_reason == "restore_incomplete_operation"
            ):
                return True
        return False

    def _is_pending_interaction_operation(self, operation: Any, session: Session) -> bool:
        pending = session.pending_interaction
        if pending is None:
            return False
        action = (
            dict(pending.request_payload.get("action") or {})
            if isinstance(pending.request_payload, dict)
            else {}
        )
        pending_call_id = str(action.get("call_id") or "")
        return bool(
            pending_call_id
            and pending_call_id == str(operation.tool_call_id or "")
            and str(pending.tool_name or "")
            == str(operation.metadata.get("tool_name") or pending.tool_name or "")
        )

    def _dispatch(self, state, input_value, observer, cancel):
        callbacks = _observer_callbacks(observer)
        workflow_state = str(
            getattr(input_value, "workflow_state", "") or self._definition.workflow_state or ""
        )
        if isinstance(input_value, UserTurn):
            initial_mode = input_value.mode or state.current_mode
            result = self._dispatcher.submit_user_turn(
                user_text=input_value.text,
                stream=input_value.stream,
                initial_mode=initial_mode,
                workflow_state=workflow_state,
                session=state.session,
                stop_event=cancel,
                **callbacks,
            )
            return result, initial_mode
        if isinstance(input_value, InteractionReply):
            pending = state.session.pending_interaction
            if pending is None or pending.interaction_id != input_value.interaction_id:
                raise ValueError("interaction id does not match")
            result = self._dispatcher.resume_interaction(
                session=state.session,
                initial_mode=state.current_mode,
                interaction_resolution=input_value.value,
                workflow_state=workflow_state,
                stream=input_value.stream,
                stop_event=cancel,
                **callbacks,
            )
            return result, state.current_mode
        raise TypeError("unsupported agent input")

    def _project_result(self, result: QueryTurnResult, initial_mode: str) -> AgentResult:
        result_mode = str(result.transition.next_mode or initial_mode or "")
        pending = (
            result.pending_interaction
            or result.transition.pending_interaction
            or result.session.pending_interaction
        )
        return AgentResult(
            final_text=result.final_text,
            session=AgentSessionView(
                session_id=str(result.session.session_id or ""),
                current_mode=result_mode,
                workflow_state=dict(result.session.workflow_state or {}),
                message_count=len(result.session.messages),
                turn_count=len(result.session.turns),
            ),
            termination_reason=result.transition.reason,
            pending_interaction=pending,
            turn_snapshot=self._dispatcher.last_turn_snapshot(),
            outcome=_json_safe(result.outcome.to_dict()),
            turns_used=int(result.turns_used or 0),
            termination_message=str(result.transition.message or ""),
        )

    def _host_dispatch(self, session_id, bound_session, current_mode, callback, *args, **kwargs):
        if not isinstance(bound_session, Session):
            raise TypeError("host session must be Session")
        context = SessionReducerContext(current_mode=str(current_mode or ""))
        with self._lease(session_id):
            with self._event_committer.bind(context):
                return callback(*args, **kwargs)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _emit(observer: AgentObserver, event_type: str, payload: Dict[str, Any]) -> None:
    observer.on_event(event_type, _json_safe(payload))


def _observer_callbacks(observer: Optional[AgentObserver]) -> Dict[str, Any]:
    if observer is None:
        return {}

    def on_text_delta(text: str) -> None:
        _emit(observer, "text.delta", {"text": text})

    def on_reasoning_delta(text: str) -> None:
        _emit(observer, "reasoning.delta", {"text": text})

    def on_tool_start(action: Action) -> None:
        _emit(
            observer,
            "tool.started",
            {
                "name": str(action.name or ""),
                "arguments": dict(action.arguments or {}),
                "callId": str(action.call_id or ""),
            },
        )

    def on_tool_finish(action: Action, observation: Observation) -> None:
        _emit(
            observer,
            "tool.finished",
            {
                "name": str(action.name or ""),
                "arguments": dict(action.arguments or {}),
                "callId": str(action.call_id or ""),
                "toolName": str(observation.tool_name or ""),
                "success": bool(observation.success),
                "error": observation.error,
                "data": observation.data,
            },
        )

    def on_context_result(result: ContextAssemblyResult) -> None:
        _emit(
            observer,
            "context.assembled",
            {
                "messageCount": len(list(result.messages or [])),
                "usedChars": int(result.used_chars or 0),
                "approxTokens": int(result.approx_tokens or 0),
                "compacted": bool(result.compacted),
                "summarizedTurns": int(result.summarized_turns or 0),
                "recentTurns": int(result.recent_turns or 0),
                "hasSummary": bool(result.summary_message),
                "pipelineSteps": list(getattr(result, "pipeline_steps", []) or []),
                "analysis": dict(getattr(result, "analysis", {}) or {}),
            },
        )

    def on_step_start(step_id: str, step_index: int) -> None:
        _emit(
            observer,
            "step.started",
            {"id": str(step_id or ""), "index": int(step_index)},
        )

    def on_step_finish(
        step_index: int,
        reply: AssistantReply,
        termination_reason: str,
    ) -> None:
        _emit(
            observer,
            "step.finished",
            {
                "index": int(step_index),
                "content": str(reply.content or ""),
                "finishReason": str(reply.finish_reason or ""),
                "terminationReason": str(termination_reason or ""),
            },
        )

    callbacks = {
        "on_text_delta": on_text_delta,
        "on_reasoning_delta": on_reasoning_delta,
        "on_tool_start": on_tool_start,
        "on_tool_finish": on_tool_finish,
        "on_context_result": on_context_result,
        "on_step_start": on_step_start,
        "on_step_finish": on_step_finish,
    }
    permission_handler = getattr(observer, "on_permission_request", None)
    if callable(permission_handler):
        callbacks["permission_handler"] = permission_handler
    user_input_handler = getattr(observer, "on_user_input_request", None)
    if callable(user_input_handler):
        callbacks["user_input_handler"] = user_input_handler
    return callbacks
