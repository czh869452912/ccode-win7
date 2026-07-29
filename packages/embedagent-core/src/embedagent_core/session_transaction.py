from __future__ import annotations

import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional

from embedagent_core.api import (
    AgentInput,
    AgentInteractionRequest,
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
from embedagent_core.session_journal import EventIntent, SessionJournal
from embedagent_core.session_operation_log import operation_diagnostics
from embedagent_core.session_reducer import SessionReducerContext
from embedagent_core.session_view import session_read_view


@dataclass(frozen=True)
class AgentRequest:
    session_id: str
    input: AgentInput


@dataclass(frozen=True)
class SessionTransactionState:
    session: Session
    current_mode: str
    reduction_context: SessionReducerContext
    restore_stop_reason: str = ""
    restore_consumed_event_count: int = 0
    restore_transcript_event_count: int = 0
    operation_diagnostics: Dict[str, Any] = field(default_factory=dict)
    runtime_config: Dict[str, Any] = field(default_factory=dict)
    compaction_state: Dict[str, Any] = field(default_factory=dict)
    recovery_state: Dict[str, Any] = field(default_factory=dict)
    turn_experience: Dict[str, Any] = field(default_factory=dict)


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
        current_mode: str,
        workflow_state: str,
    ) -> Any:
        def initialize(state: SessionTransactionState) -> Any:
            previous_mode = state.current_mode
            mode = self._dispatcher.initialize_session(
                state.session,
                current_mode,
                workflow_state=workflow_state,
            )
            if state.restore_transcript_event_count and mode != previous_mode:
                self._commit_host_mode(state, mode)
            if state.restore_transcript_event_count:
                event_count = len(self._session_log.load_events(state.session.session_id))
                self._journal.commit(
                    state.session,
                    state.reduction_context,
                    (
                        EventIntent(
                            "recovery_marker",
                            {
                                "marker_id": "recovery-" + uuid.uuid4().hex,
                                "reason": "resume",
                                "status": "clean",
                                "current_mode": mode,
                                "trusted_event_count": event_count,
                                "transcript_event_count": event_count,
                                "stop_reason": "",
                                "skipped_count": 0,
                                "skip_reasons": [],
                                "operation_summary": dict(state.operation_diagnostics),
                                "compaction_summary": dict(state.compaction_state),
                                "runtime_summary": dict(state.runtime_config),
                                "metadata": {"source": "HostedSessionController.initialize"},
                            },
                        ),
                    ),
                )
            return self._project_hosted(state, mode)

        return self._host_transaction(session_id, initialize)

    def apply_host_mode(
        self,
        session_id: str,
        mode: str,
        workflow_state: str,
    ) -> Any:
        def apply(state: SessionTransactionState) -> Any:
            applied = self._dispatcher.apply_mode(
                state.session,
                mode,
                workflow_state=workflow_state,
            )
            if applied != state.current_mode:
                self._commit_host_mode(state, applied)
            return self._project_hosted(state, applied)

        return self._host_transaction(session_id, apply)

    def record_host_command(self, session_id: str, **kwargs: Any) -> Any:
        def record(state: SessionTransactionState) -> Any:
            self._dispatcher.record_command_result(state.session, **kwargs)
            return self._project_hosted(state, state.reduction_context.current_mode)

        return self._host_transaction(session_id, record)

    def submit_host_command(self, session_id: str, **kwargs: Any) -> Any:
        def submit(state: SessionTransactionState) -> Any:
            arguments = dict(kwargs)
            arguments.pop("session", None)
            arguments["session"] = state.session
            arguments.setdefault("initial_mode", state.current_mode)
            result, observation = self._dispatcher.submit_command_turn(**arguments)
            return self._project_host_command(state, result, observation)

        return self._host_transaction(session_id, submit)

    def resume_host_command(self, session_id: str, **kwargs: Any) -> Any:
        def resume(state: SessionTransactionState) -> Any:
            arguments = dict(kwargs)
            arguments.pop("session", None)
            arguments["session"] = state.session
            arguments.setdefault("initial_mode", state.current_mode)
            result = self._dispatcher.resume_interaction(**arguments)
            observation = None
            if result.session.turns and result.session.turns[-1].observations:
                observation = result.session.turns[-1].observations[-1]
            return self._project_host_command(state, result, observation)

        return self._host_transaction(session_id, resume)

    def update_host_resource_prompt(self, session_id: str, **kwargs: Any) -> Any:
        def update(state: SessionTransactionState) -> Any:
            content = str(kwargs.get("content") or "")
            previous = None
            for message in reversed(state.session.messages):
                if (
                    str(getattr(message, "role", "") or "") == "system"
                    and str(getattr(message, "kind", "") or "") == "local_skills_prompt"
                    and not bool(getattr(message, "archived", False))
                ):
                    previous = message
                    break
            if previous is not None and str(previous.content or "") == content:
                return self._project_hosted(state, state.current_mode)
            parent_message_id = ""
            for message in reversed(state.session.messages):
                if not bool(getattr(message, "archived", False)) and message is not previous:
                    parent_message_id = str(getattr(message, "message_id", "") or "")
                    break
            self._journal.commit(
                state.session,
                state.reduction_context,
                (
                    EventIntent(
                        "message",
                        {
                            "role": "system",
                            "content": content,
                            "message_id": "m-" + uuid.uuid4().hex[:12] if content else "",
                            "parent_message_id": parent_message_id,
                            "turn_id": "",
                            "step_id": "",
                            "kind": "local_skills_prompt",
                            "metadata": {
                                "reason": str(kwargs.get("reason") or ""),
                                "resource_revision": int(kwargs.get("revision") or 0),
                            },
                            "replace_kind": True,
                            "remove_only": not bool(content),
                        },
                    ),
                ),
            )
            return self._project_hosted(state, state.current_mode)

        return self._host_transaction(session_id, update)

    def snapshot_host(self, session_id: str) -> Any:
        return self._host_transaction(
            session_id,
            lambda state: self._project_hosted(state, state.current_mode),
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
            restore_stop_reason=str(restored.stop_reason or ""),
            restore_consumed_event_count=int(restored.consumed_event_count or 0),
            restore_transcript_event_count=int(restored.transcript_event_count or 0),
            operation_diagnostics=operation_diagnostics(restored.operation_state),
            runtime_config=_state_dict(restored.runtime_config),
            compaction_state=_state_dict(restored.compaction_state),
            recovery_state=_state_dict(restored.recovery_state),
            turn_experience=_state_dict(restored.turn_experience),
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
            pending_interaction=_project_interaction(pending),
            turn_snapshot=self._dispatcher.last_turn_snapshot(),
            outcome=_json_safe(result.outcome.to_dict()),
            turns_used=int(result.turns_used or 0),
            termination_message=str(result.transition.message or ""),
        )

    def _host_transaction(self, session_id: str, callback: Any) -> Any:
        with self._lease(session_id):
            state = self._restore_or_create(session_id)
            with self._event_committer.bind(state.reduction_context):
                return callback(state)

    def _commit_host_mode(self, state: SessionTransactionState, mode: str) -> None:
        self._journal.commit(
            state.session,
            state.reduction_context,
            (
                EventIntent(
                    "session_meta",
                    {
                        "current_mode": str(mode or ""),
                        "started_at": state.session.started_at,
                    },
                ),
            ),
        )

    def _project_hosted(self, state: SessionTransactionState, current_mode: str) -> Any:
        from embedagent_core.hosting import HostedSessionProjection

        view = session_read_view(state.session)
        pending = _project_interaction(state.session.pending_interaction)
        status = "idle"
        if pending is not None and pending.kind == "permission":
            status = "waiting_permission"
        elif pending is not None and pending.kind == "user_input":
            status = "waiting_user_input"
        event_count = len(self._session_log.load_events(state.session.session_id))
        snapshot = {
            "session_id": view.session_id,
            "current_mode": str(current_mode or state.reduction_context.current_mode or ""),
            "status": status,
            "started_at": view.started_at,
            "workflow_state": _json_safe(view.workflow_state),
            "message_count": len(view.messages),
            "turn_count": len(view.turns),
            "compact_boundary_count": len(view.compact_boundaries),
            "pending_interaction": _json_safe(view.pending_interaction),
            "restore_stop_reason": state.restore_stop_reason,
            "restore_consumed_event_count": event_count,
            "restore_transcript_event_count": event_count,
            "operation_diagnostics": _json_safe(state.operation_diagnostics),
            "runtime_config": _json_safe(state.runtime_config),
            "compaction_state": _json_safe(state.compaction_state),
            "recovery_state": _json_safe(state.recovery_state),
            "turn_experience": _json_safe(state.turn_experience),
        }
        history = {
            "session_id": view.session_id,
            "messages": _json_safe(view.messages),
            "turns": _json_safe(view.turns),
            "workflow_state": _json_safe(view.workflow_state),
            "compact_boundaries": _json_safe(view.compact_boundaries),
            "current_interaction": _json_safe(view.pending_interaction),
        }
        return HostedSessionProjection(
            session_id=view.session_id,
            current_mode=str(snapshot["current_mode"]),
            status=status,
            pending_interaction=pending,
            snapshot=snapshot,
            history=history,
        )

    def _project_host_command(
        self,
        state: SessionTransactionState,
        result: QueryTurnResult,
        observation: Optional[Observation],
    ) -> Any:
        from embedagent_core.hosting import HostedCommandResult

        next_mode = str(
            result.transition.next_mode
            or state.reduction_context.current_mode
            or state.current_mode
        )
        return HostedCommandResult(
            projection=self._project_hosted(state, next_mode),
            termination_reason=str(result.transition.reason or ""),
            termination_message=str(result.transition.message or ""),
            next_mode=next_mode,
            turns_used=int(result.turns_used or 0),
            observation=(
                {
                    "tool_name": str(observation.tool_name or ""),
                    "success": bool(observation.success),
                    "error": observation.error,
                    "data": _json_safe(observation.data),
                }
                if observation is not None
                else None
            ),
        )


def _project_interaction(pending: Any) -> Optional[AgentInteractionRequest]:
    if pending is None:
        return None
    return AgentInteractionRequest(
        interaction_id=str(getattr(pending, "interaction_id", "") or ""),
        kind=str(getattr(pending, "kind", "") or ""),
        tool_name=str(getattr(pending, "tool_name", "") or ""),
        request_payload=dict(getattr(pending, "request_payload", {}) or {}),
    )


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _state_dict(value: Any) -> Dict[str, Any]:
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        return dict(payload) if isinstance(payload, dict) else {}
    return {}


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
