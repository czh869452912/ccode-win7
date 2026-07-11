from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Optional

from embedagent_core.api import (
    AgentInput,
    AgentObserver,
    AgentPorts,
    AgentResult,
    AgentRuntimeServices,
    AgentSessionView,
    CancelToken,
    InteractionReply,
    RuntimeDefinition,
    UserTurn,
)
from embedagent_core.extensions import ExtensionManager
from embedagent_core.query_engine import QueryEngine
from embedagent_core.session import (
    Action,
    AssistantReply,
    ContextAssemblyResult,
    Observation,
    QueryTurnResult,
    Session,
)
from embedagent_core.session_restore import SessionRestorer


@dataclass(frozen=True)
class AgentRequest:
    session_id: str
    input: AgentInput


@dataclass(frozen=True)
class AgentRunState:
    public_result: AgentResult
    query_result: QueryTurnResult
    current_mode: str
    turn_snapshot: Any


class SessionRecoveryRequired(RuntimeError):
    def __init__(self, session_id: str, stop_reason: str) -> None:
        self.session_id = str(session_id or "")
        self.stop_reason = str(stop_reason or "incomplete_transcript")
        super(SessionRecoveryRequired, self).__init__(
            "session recovery required for %s: %s" % (self.session_id, self.stop_reason)
        )


class AgentRuntime(object):
    def __init__(self, ports: AgentPorts, definition: RuntimeDefinition) -> None:
        self.ports = ports
        self.definition = definition
        self.extension_manager = ports.extension_manager or ExtensionManager(
            list(definition.extensions)
        )
        self._host_lease_state = threading.local()

    def _services(self) -> AgentRuntimeServices:
        services = self.ports.runtime_services
        if services is None:
            return AgentRuntimeServices()
        if not isinstance(services, AgentRuntimeServices):
            raise TypeError("runtime services must be AgentRuntimeServices")
        return services

    def build_engine(self) -> QueryEngine:
        services = self._services()
        return QueryEngine(
            client=self.ports.model,
            tools=self.ports.tools,
            max_turns=services.max_turns,
            permission_policy=self.ports.permissions,
            context_manager=self.ports.context,
            summary_store=services.summary_store,
            project_memory_store=services.project_memory_store,
            memory_maintenance=services.memory_maintenance,
            maintenance_interval=services.maintenance_interval,
            intelligence_broker=services.intelligence_broker,
            transcript_store=self.ports.session_log,
            extension_manager=self.extension_manager,
            remembered_permission_categories_provider=(
                services.remembered_permission_categories_provider
            ),
            mode_tool_policy=self.definition.mode_tool_policy,
            write_path_policy=self.definition.write_path_policy,
            mode_runtime_policy=self.definition.mode_runtime_policy,
            tool_commit=services.tool_commit,
            workspace_profile=services.workspace_profile,
        )

    def workflow_state(self, session_id: str) -> str:
        provider = self._services().workflow_state_provider
        if callable(provider):
            return str(provider(session_id) or self.definition.workflow_state or "")
        return str(self.definition.workflow_state or "")

    def restore_best_effort(self, session_id: str) -> bool:
        provider = self._services().restore_best_effort_provider
        return bool(provider(session_id)) if callable(provider) else False

    @contextmanager
    def _host_lease(self, session_id: str) -> Iterator[None]:
        depths = getattr(self._host_lease_state, "depths", None)
        if depths is None:
            depths = {}
            self._host_lease_state.depths = depths
        depth = int(depths.get(session_id, 0) or 0)
        if depth:
            depths[session_id] = depth + 1
            try:
                yield
            finally:
                depths[session_id] -= 1
            return
        with self.ports.session_log.acquire_lease(session_id):
            depths[session_id] = 1
            try:
                yield
            finally:
                depths.pop(session_id, None)

    def host_initialize_session(
        self,
        session_id: str,
        session: Session,
        current_mode: str,
        workflow_state: str,
    ) -> str:
        with self._host_lease(session_id):
            return self.build_engine().initialize_session(
                session,
                current_mode,
                workflow_state=workflow_state,
            )

    def host_apply_mode(
        self,
        session_id: str,
        session: Session,
        mode: str,
        workflow_state: str,
    ) -> str:
        with self._host_lease(session_id):
            return self.build_engine().apply_mode(
                session,
                mode,
                workflow_state=workflow_state,
            )

    def host_record_command_result(
        self,
        session_id: str,
        session: Session,
        **kwargs: Any,
    ) -> None:
        with self._host_lease(session_id):
            self.build_engine().record_command_result(session, **kwargs)

    def host_record_pending_permission(
        self,
        session_id: str,
        session: Session,
        action: Action,
        permission_payload: Dict[str, Any],
        current_mode: str,
        interaction_id: str = "",
    ) -> None:
        with self._host_lease(session_id):
            self.build_engine().kernel.record_pending_permission(
                session,
                action,
                permission_payload,
                current_mode,
                interaction_id=interaction_id,
            )

    def host_submit_command_turn(self, session_id: str, **kwargs: Any) -> Any:
        with self._host_lease(session_id):
            return self.build_engine().submit_command_turn(**kwargs)

    def host_resume_command_interaction(self, session_id: str, **kwargs: Any) -> Any:
        with self._host_lease(session_id):
            return self.build_engine().resume_interaction(**kwargs)


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

    callbacks = {}
    fallback_callbacks = {
        "on_text_delta": on_text_delta,
        "on_reasoning_delta": on_reasoning_delta,
        "on_tool_start": on_tool_start,
        "on_tool_finish": on_tool_finish,
        "on_context_result": on_context_result,
        "on_step_start": on_step_start,
        "on_step_finish": on_step_finish,
    }
    for callback_name, fallback in fallback_callbacks.items():
        direct_callback = getattr(observer, callback_name, None)
        callbacks[callback_name] = direct_callback if callable(direct_callback) else fallback
    permission_handler = getattr(observer, "on_permission_request", None)
    if callable(permission_handler):
        callbacks["permission_handler"] = permission_handler
    user_input_handler = getattr(observer, "on_user_input_request", None)
    if callable(user_input_handler):
        callbacks["user_input_handler"] = user_input_handler
    return callbacks


def _session_view(session: Session, current_mode: str) -> AgentSessionView:
    return AgentSessionView(
        session_id=str(session.session_id or ""),
        current_mode=str(current_mode or ""),
        workflow_state=dict(session.workflow_state or {}),
        message_count=len(session.messages),
        turn_count=len(session.turns),
    )


def _result_mode(result: QueryTurnResult, initial_mode: str) -> str:
    return str(result.transition.next_mode or initial_mode or "")


def _result_pending_interaction(result: QueryTurnResult) -> Any:
    return (
        result.pending_interaction
        or result.transition.pending_interaction
        or result.session.pending_interaction
    )


def run_agent_with_state(
    runtime: AgentRuntime,
    request: AgentRequest,
    observer: Optional[AgentObserver] = None,
    cancel: Optional[CancelToken] = None,
) -> AgentRunState:
    session_id = str(request.session_id or "").strip()
    callbacks = _observer_callbacks(observer)
    session_log = runtime.ports.session_log
    with session_log.acquire_lease(session_id):
        if session_log.transcript_exists(session_id):
            events = session_log.load_events(session_id)
            restored = SessionRestorer().restore(
                events,
                best_effort=runtime.restore_best_effort(session_id),
            )
            if restored.stop_reason or restored.consumed_event_count != len(events):
                raise SessionRecoveryRequired(session_id, restored.stop_reason)
            session = restored.session
            current_mode = restored.current_mode
        else:
            session = Session(session_id=session_id)
            current_mode = runtime.definition.default_mode

        engine = runtime.build_engine()
        workflow_state = runtime.workflow_state(session_id)
        input_value = request.input
        if isinstance(input_value, UserTurn):
            initial_mode = input_value.mode or current_mode
            result = engine.submit_user_turn(
                user_text=input_value.text,
                stream=input_value.stream,
                initial_mode=initial_mode,
                workflow_state=workflow_state,
                session=session,
                stop_event=cancel,
                **callbacks,
            )
        elif isinstance(input_value, InteractionReply):
            pending = session.pending_interaction
            if pending is None or pending.interaction_id != input_value.interaction_id:
                raise ValueError("interaction id does not match")
            initial_mode = current_mode
            result = engine.resume_interaction(
                session=session,
                initial_mode=initial_mode,
                interaction_resolution=input_value.value,
                workflow_state=workflow_state,
                stream=input_value.stream,
                stop_event=cancel,
                **callbacks,
            )
        else:
            raise TypeError("unsupported agent input")

        result_mode = _result_mode(result, initial_mode)
        public_result = AgentResult(
            final_text=result.final_text,
            session=_session_view(result.session, result_mode),
            termination_reason=result.transition.reason,
            pending_interaction=_result_pending_interaction(result),
            turn_snapshot=engine.last_turn_snapshot(),
        )
        return AgentRunState(
            public_result=public_result,
            query_result=result,
            current_mode=result_mode,
            turn_snapshot=engine.last_turn_snapshot(),
        )


def run_agent(
    runtime: AgentRuntime,
    request: AgentRequest,
    observer: Optional[AgentObserver] = None,
    cancel: Optional[CancelToken] = None,
) -> AgentResult:
    return run_agent_with_state(
        runtime,
        request,
        observer=observer,
        cancel=cancel,
    ).public_result
