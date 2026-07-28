from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from embedagent_core.agent_effects import (
    AssembleContextEffect,
    ContextAssembled,
    EffectFailed,
    ProviderCompleted,
    RequestProviderEffect,
)
from embedagent_core.model import ModelClient, ModelClientError
from embedagent_core.ports import ContextAssemblerPort
from embedagent_core.session import AssistantReply, ContextAssemblyResult, Session
from embedagent_core.session_journal import EventIntent
from embedagent_core.session_log import SessionLogPort
from embedagent_core.strategies.llm_retry_wrapper import LLMClientRetryWrapper
from embedagent_core.turn_snapshot import TurnSnapshot
from embedagent_core.turn_snapshot_service import TurnSnapshotService

_COMPACT_RETRY_ERROR_MARKERS = (
    "context length",
    "maximum context",
    "prompt is too long",
    "prompt too long",
    "max tokens",
    "too many tokens",
    "上下文",
    "超出上下文",
)


@dataclass(frozen=True)
class ProviderObserver:
    on_text_delta: Optional[Callable[[str], None]] = None
    on_reasoning_delta: Optional[Callable[[str], None]] = None


class ProviderStepService(object):
    """Executes context and provider effects without committing session state."""

    def __init__(
        self,
        context_assembler: ContextAssemblerPort,
        extension_host: Any,
        snapshot_service: TurnSnapshotService,
        tools: Any,
        client: ModelClient,
        session_log: SessionLogPort,
        retry_max_attempts: int = 3,
        retry_base_delay: float = 1.0,
    ) -> None:
        self._context_assembler = context_assembler
        self._extension_host = extension_host
        self._snapshot_service = snapshot_service
        self._tools = tools
        self._client = client
        self._session_log = session_log
        self._provider = LLMClientRetryWrapper(
            client=client,
            max_retries=max(1, int(retry_max_attempts)),
            base_delay=max(0.0, float(retry_base_delay)),
        )
        self._last_snapshot = None  # type: Optional[TurnSnapshot]

    def last_snapshot(self) -> Optional[TurnSnapshot]:
        return self._last_snapshot

    def assemble_context(self, effect: AssembleContextEffect, session: Session) -> ContextAssembled:
        assembly = self._context_assembler.build_messages(
            session,
            effect.mode_name,
            tools=self._tools,
            workflow_state=effect.workflow_state,
            force_compact=effect.force_compact,
        )
        assembly = self._normalize_assembly(assembly)
        assembly = self._extension_host.apply_context_patch(
            session,
            effect.mode_name,
            effect.workflow_state,
            assembly,
            force_compact=effect.force_compact,
        )
        tool_schemas = self._extension_host.schemas_for_active_tools(
            effect.mode_name,
            effect.workflow_state,
        )
        snapshot = self._snapshot_service.build_provider_snapshot(
            session=session,
            turn_id=effect.turn_id,
            step_id=effect.step_id,
            mode_name=effect.mode_name,
            workflow_state=effect.workflow_state,
            messages=assembly.messages,
            tool_schemas=tool_schemas,
            tools=self._tools,
            client=self._client,
            transcript_store=self._session_log,
        )
        self._last_snapshot = snapshot
        return ContextAssembled(
            effect.effect_id,
            assembly,
            snapshot,
            events=self._context_events(effect, assembly),
        )

    def request_provider(
        self,
        effect: RequestProviderEffect,
        observer: Optional[ProviderObserver],
    ):
        observer = observer or ProviderObserver()
        try:
            reply = self._provider.call_with_retry(
                messages=effect.snapshot.messages,
                tools=effect.snapshot.tool_schemas,
                stream=effect.stream,
                on_text_delta=observer.on_text_delta,
                on_reasoning_delta=observer.on_reasoning_delta,
            )
        except ModelClientError as exc:
            error_kind = "context_limit" if self._is_context_limit(exc) else "provider_error"
            return EffectFailed(
                effect.effect_id,
                error_kind,
                str(exc),
                retryable=False,
                events=(self._provider_interrupted_event(effect, error_kind, str(exc)),),
            )
        return ProviderCompleted(
            effect.effect_id,
            reply,
            events=(self._provider_finished_event(effect, reply),),
        )

    def _normalize_assembly(self, build: Any) -> ContextAssemblyResult:
        if isinstance(build, ContextAssemblyResult):
            return build
        return ContextAssemblyResult(
            messages=build.messages,
            used_chars=build.used_chars,
            approx_tokens=build.approx_tokens,
            compacted=build.compacted,
            summarized_turns=build.summarized_turns,
            recent_turns=build.recent_turns,
            policy=build.policy,
            budget=build.budget,
            stats=build.stats,
            summary_message=getattr(build, "summary_message", ""),
            intelligence_sections=getattr(build, "intelligence_sections", []),
            analysis=getattr(build, "analysis", {}),
            replacements=getattr(build, "replacements", []),
            pipeline_steps=getattr(build, "pipeline_steps", []),
            plan=getattr(build, "plan", None),
        )

    def _context_events(
        self,
        effect: AssembleContextEffect,
        assembly: ContextAssemblyResult,
    ) -> Tuple[EventIntent, ...]:
        snapshot_operation_id = "context_snapshot:%s" % effect.effect_id
        snapshot_payload = self._context_snapshot_payload(effect.mode_name, assembly)
        events = [
            EventIntent(
                "operation_finished",
                self._operation_payload(
                    effect.effect_id,
                    "context_assembly",
                    effect.turn_id,
                    effect.step_id,
                    result=self._context_operation_result(assembly),
                ),
            ),
            EventIntent(
                "operation_started",
                self._operation_payload(
                    snapshot_operation_id,
                    "context_snapshot",
                    effect.turn_id,
                    effect.step_id,
                    metadata={
                        "mode_name": effect.mode_name,
                        "workflow_state": effect.workflow_state,
                    },
                ),
            ),
            EventIntent("context_snapshot", snapshot_payload),
            EventIntent(
                "operation_finished",
                self._operation_payload(
                    snapshot_operation_id,
                    "context_snapshot",
                    effect.turn_id,
                    effect.step_id,
                    result=snapshot_payload,
                ),
            ),
        ]
        for replacement in list(assembly.replacements or []):
            events.append(EventIntent("content_replacement", dict(replacement)))
        return tuple(events)

    def _provider_finished_event(
        self,
        effect: RequestProviderEffect,
        reply: AssistantReply,
    ) -> EventIntent:
        snapshot_metadata = self._snapshot_service.metadata(effect.snapshot)
        return EventIntent(
            "operation_finished",
            self._operation_payload(
                effect.effect_id,
                "provider_request",
                effect.snapshot.turn_id,
                effect.snapshot.step_id,
                result={
                    "finish_reason": reply.finish_reason,
                    "action_count": len(reply.actions),
                    "content_length": len(reply.content or ""),
                    "reasoning_length": len(reply.reasoning_content or ""),
                    "turn_snapshot": snapshot_metadata,
                },
            ),
        )

    def _provider_interrupted_event(
        self,
        effect: RequestProviderEffect,
        reason: str,
        message: str,
    ) -> EventIntent:
        return EventIntent(
            "operation_interrupted",
            self._operation_payload(
                effect.effect_id,
                "provider_request",
                effect.snapshot.turn_id,
                effect.snapshot.step_id,
                reason=reason,
                result={"error": message},
            ),
        )

    def _operation_payload(
        self,
        operation_id: str,
        kind: str,
        turn_id: str,
        step_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        reason: str = "",
    ) -> Dict[str, Any]:
        payload = {
            "operation_id": operation_id,
            "kind": kind,
            "turn_id": turn_id,
            "step_id": step_id,
        }  # type: Dict[str, Any]
        if metadata is not None:
            payload["metadata"] = dict(metadata)
        if result is not None:
            payload["result"] = dict(result)
        if reason:
            payload["reason"] = reason
            payload["retryable"] = False
        return payload

    def _context_operation_result(self, assembly: ContextAssemblyResult) -> Dict[str, Any]:
        return {
            "approx_tokens": assembly.approx_tokens,
            "used_chars": assembly.used_chars,
            "compacted": assembly.compacted,
            "summarized_turns": assembly.summarized_turns,
            "recent_turns": assembly.recent_turns,
            "pipeline_steps": list(assembly.pipeline_steps),
            "replacements": len(assembly.replacements),
            "context_plan": self._context_plan_payload(assembly),
        }

    def _context_snapshot_payload(
        self,
        mode_name: str,
        assembly: ContextAssemblyResult,
    ) -> Dict[str, Any]:
        return {
            "mode_name": mode_name,
            "pipeline_steps": list(assembly.pipeline_steps),
            "analysis": dict(assembly.analysis),
            "approx_tokens": assembly.approx_tokens,
            "summary_message": assembly.summary_message,
            "context_plan": self._context_plan_payload(assembly),
        }

    def _context_plan_payload(self, assembly: ContextAssemblyResult) -> Dict[str, Any]:
        plan = getattr(assembly, "plan", None)
        if plan is None:
            return {}
        to_metadata = getattr(plan, "to_boundary_metadata", None)
        if callable(to_metadata):
            return dict(to_metadata())
        return {}

    def _is_context_limit(self, exc: ModelClientError) -> bool:
        message = str(exc or "").lower()
        return any(marker in message for marker in _COMPACT_RETRY_ERROR_MARKERS)
