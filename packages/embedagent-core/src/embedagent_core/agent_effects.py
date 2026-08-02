from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple, Union

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

    def presentation(self) -> Dict[str, Any]:
        value = json.loads(self.presentation_json)
        return dict(value) if isinstance(value, dict) else {}


@dataclass(frozen=True)
class ImmediateToolResult:
    source_index: int
    original_action: FrozenToolAction
    effective_action: FrozenToolAction
    observation: Observation


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


@dataclass(frozen=True)
class ExecutePreparedToolBatchEffect:
    effect_id: str
    invocations: Tuple[PreparedToolInvocation, ...]
    immediate_results: Tuple[ImmediateToolResult, ...] = field(default_factory=tuple)


def _tool_invocation_id(assistant_message_id: str, source_index: int) -> str:
    return "tool:%s:%d" % (assistant_message_id, source_index)


@dataclass(frozen=True)
class ExecuteToolBatchEffect:
    effect_id: str
    actions: Tuple[Action, ...]
    mode_name: str
    workflow_state: str


AgentEffect = Union[
    AssembleContextEffect,
    RequestProviderEffect,
    PrepareToolBatchEffect,
    ExecutePreparedToolBatchEffect,
    ExecuteToolBatchEffect,
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
