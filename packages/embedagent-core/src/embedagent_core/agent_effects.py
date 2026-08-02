from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, Union

from embedagent_core.session import (
    Action,
    AssistantReply,
    ContextAssemblyResult,
    Observation,
    PendingInteraction,
)
from embedagent_core.session_journal import EventIntent
from embedagent_core.turn_snapshot import TurnSnapshot


@dataclass(frozen=True)
class AssembleContextEffect:
    effect_id: str
    turn_id: str
    step_id: str
    mode_name: str
    workflow_state: str
    force_compact: bool = False


@dataclass(frozen=True)
class RequestProviderEffect:
    effect_id: str
    snapshot: TurnSnapshot
    stream: bool
    deferred_events: Tuple[EventIntent, ...] = field(default_factory=tuple)
    compaction_generation: int = 0


@dataclass(frozen=True)
class FrozenToolAction:
    name: str
    arguments_json: str
    call_id: str
    raw_arguments: str = ""

    @classmethod
    def from_action(cls, action: Action) -> "FrozenToolAction":
        return cls(
            action.name,
            json.dumps(
                action.arguments,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            action.call_id,
            action.raw_arguments,
        )

    def to_action(self) -> Action:
        return Action(
            self.name,
            json.loads(self.arguments_json),
            self.call_id,
            self.raw_arguments,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "arguments": json.loads(self.arguments_json),
            "call_id": self.call_id,
            "raw_arguments": self.raw_arguments,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "FrozenToolAction":
        return cls.from_action(
            Action(
                str(payload.get("name") or ""),
                dict(payload.get("arguments") or {}),
                str(payload.get("call_id") or ""),
                str(payload.get("raw_arguments") or ""),
            )
        )


@dataclass(frozen=True)
class PreparedToolInvocation:
    invocation_id: str
    provider_call_id: str
    source_index: int
    original_action: FrozenToolAction
    effective_action: FrozenToolAction
    permission_category: str
    read_only: bool
    concurrency_safe: bool
    presentation_json: str
    source_type: str
    source_id: str
    replay_safe: bool
    mode_name: str = ""
    workflow_state: str = ""

    def presentation(self) -> Dict[str, Any]:
        value = json.loads(self.presentation_json)
        return dict(value) if isinstance(value, dict) else {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invocation_id": self.invocation_id,
            "provider_call_id": self.provider_call_id,
            "source_index": self.source_index,
            "original_action": self.original_action.to_dict(),
            "effective_action": self.effective_action.to_dict(),
            "permission_category": self.permission_category,
            "read_only": self.read_only,
            "concurrency_safe": self.concurrency_safe,
            "presentation": self.presentation(),
            "source_type": self.source_type,
            "source_id": self.source_id,
            "replay_safe": self.replay_safe,
            "mode_name": self.mode_name,
            "workflow_state": self.workflow_state,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PreparedToolInvocation":
        return cls(
            invocation_id=str(payload.get("invocation_id") or ""),
            provider_call_id=str(payload.get("provider_call_id") or ""),
            source_index=int(payload.get("source_index") or 0),
            original_action=FrozenToolAction.from_dict(dict(payload.get("original_action") or {})),
            effective_action=FrozenToolAction.from_dict(
                dict(payload.get("effective_action") or {})
            ),
            permission_category=str(payload.get("permission_category") or "other"),
            read_only=bool(payload.get("read_only")),
            concurrency_safe=bool(payload.get("concurrency_safe")),
            presentation_json=json.dumps(
                dict(payload.get("presentation") or {}),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            source_type=str(payload.get("source_type") or ""),
            source_id=str(payload.get("source_id") or ""),
            replay_safe=bool(payload.get("replay_safe")),
            mode_name=str(payload.get("mode_name") or ""),
            workflow_state=str(payload.get("workflow_state") or ""),
        )


@dataclass(frozen=True)
class ImmediateToolResult:
    source_index: int
    original_action: FrozenToolAction
    effective_action: FrozenToolAction
    observation: Observation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_index": self.source_index,
            "original_action": self.original_action.to_dict(),
            "effective_action": self.effective_action.to_dict(),
            "observation": self.observation.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ImmediateToolResult":
        effective_action = FrozenToolAction.from_dict(dict(payload.get("effective_action") or {}))
        observation = dict(payload.get("observation") or {})
        return cls(
            source_index=int(payload.get("source_index") or 0),
            original_action=FrozenToolAction.from_dict(dict(payload.get("original_action") or {})),
            effective_action=effective_action,
            observation=Observation(
                str(observation.get("tool_name") or effective_action.name),
                bool(observation.get("success")),
                observation.get("error"),
                observation.get("data"),
            ),
        )


@dataclass(frozen=True)
class PrepareToolBatchEffect:
    effect_id: str
    assistant_message_id: str
    actions: Tuple[FrozenToolAction, ...]
    mode_name: str
    workflow_state: str
    provider_truncated: bool = False
    start_index: int = 0
    prepared_prefix: Tuple[PreparedToolInvocation, ...] = field(default_factory=tuple)
    immediate_prefix: Tuple[ImmediateToolResult, ...] = field(default_factory=tuple)
    continuation: str = "context"
    resume_kind: str = ""
    resume_effective_action: Optional[FrozenToolAction] = None
    resume_resolution_json: str = ""
    resume_permission_category: str = ""


@dataclass(frozen=True)
class ExecutePreparedToolBatchEffect:
    effect_id: str
    invocations: Tuple[PreparedToolInvocation, ...]
    immediate_results: Tuple[ImmediateToolResult, ...] = field(default_factory=tuple)


def _tool_invocation_id(assistant_message_id: str, source_index: int) -> str:
    return "tool:%s:%d" % (assistant_message_id, source_index)


AgentEffect = Union[
    AssembleContextEffect,
    RequestProviderEffect,
    PrepareToolBatchEffect,
    ExecutePreparedToolBatchEffect,
]


@dataclass(frozen=True)
class ContextAssembled:
    effect_id: str
    assembly: ContextAssemblyResult
    snapshot: TurnSnapshot
    events: Tuple[EventIntent, ...] = field(default_factory=tuple)
    deferred_events: Tuple[EventIntent, ...] = field(default_factory=tuple)
    compaction_generation: int = 0


@dataclass(frozen=True)
class ProviderCompleted:
    effect_id: str
    reply: AssistantReply
    events: Tuple[EventIntent, ...] = field(default_factory=tuple)
    tool_presentations: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    parent_message_id: str = ""


@dataclass(frozen=True)
class ToolBatchPrepared:
    effect_id: str
    invocations: Tuple[PreparedToolInvocation, ...] = field(default_factory=tuple)
    immediate_results: Tuple[ImmediateToolResult, ...] = field(default_factory=tuple)
    events: Tuple[EventIntent, ...] = field(default_factory=tuple)
    commit_tokens: Tuple[Any, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ToolBatchCompleted:
    effect_id: str
    observations: Tuple[Observation, ...] = field(default_factory=tuple)
    events: Tuple[EventIntent, ...] = field(default_factory=tuple)
    commit_tokens: Tuple[Any, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class InteractionSuspended:
    effect_id: str
    pending: PendingInteraction
    events: Tuple[EventIntent, ...] = field(default_factory=tuple)
    commit_tokens: Tuple[Any, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EffectFailed:
    effect_id: str
    error_kind: str
    message: str
    retryable: bool = False
    events: Tuple[EventIntent, ...] = field(default_factory=tuple)
    commit_tokens: Tuple[Any, ...] = field(default_factory=tuple)
    metadata: Dict[str, Any] = field(default_factory=dict)


AgentEffectResult = Union[
    ContextAssembled,
    ProviderCompleted,
    ToolBatchCompleted,
    InteractionSuspended,
    ToolBatchPrepared,
    EffectFailed,
]
