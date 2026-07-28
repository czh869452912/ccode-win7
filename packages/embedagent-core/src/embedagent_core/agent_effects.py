from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Tuple, Union

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


@dataclass(frozen=True)
class ExecuteToolBatchEffect:
    effect_id: str
    actions: Tuple[Action, ...]
    mode_name: str
    workflow_state: str


AgentEffect = Union[
    AssembleContextEffect,
    RequestProviderEffect,
    ExecuteToolBatchEffect,
]


@dataclass(frozen=True)
class ContextAssembled:
    effect_id: str
    assembly: ContextAssemblyResult
    snapshot: TurnSnapshot
    events: Tuple[EventIntent, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ProviderCompleted:
    effect_id: str
    reply: AssistantReply
    events: Tuple[EventIntent, ...] = field(default_factory=tuple)


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


@dataclass(frozen=True)
class EffectFailed:
    effect_id: str
    error_kind: str
    message: str
    retryable: bool = False
    events: Tuple[EventIntent, ...] = field(default_factory=tuple)


AgentEffectResult = Union[
    ContextAssembled,
    ProviderCompleted,
    ToolBatchCompleted,
    InteractionSuspended,
    EffectFailed,
]
