from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

CONTINUATION_CONTINUE = "continue"
CONTINUATION_STOP = "stop"
CONTINUATION_ABORT = "abort"
CONTINUATION_WAIT = "wait"
CONTINUATION_COMPACT_THEN_CONTINUE = "compact_then_continue"


@dataclass
class AgentLoopContinuationFacts:
    step_index: int = 0
    turns_used: int = 0
    mode_name: str = ""
    workflow_state: str = ""
    has_tool_calls: bool = False
    completion_signal: bool = False
    stop_event_set: bool = False
    safety_limit: Optional[int] = None
    safety_limit_reached: bool = False
    compacted: bool = False
    pending_interaction_reason: str = ""
    guard_stop_reason: str = ""


@dataclass
class AgentLoopContinuationDecision:
    kind: str
    reason: str = ""
    message: str = ""
    next_mode: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentLoopContinuationPolicy(object):
    def decide_after_step(
        self, facts: AgentLoopContinuationFacts
    ) -> AgentLoopContinuationDecision:
        raise NotImplementedError


class DefaultAgentLoopContinuationPolicy(AgentLoopContinuationPolicy):
    def decide_after_step(
        self, facts: AgentLoopContinuationFacts
    ) -> AgentLoopContinuationDecision:
        if facts.stop_event_set:
            return AgentLoopContinuationDecision(
                kind=CONTINUATION_ABORT,
                reason="aborted",
                message="stop_event set",
            )
        if facts.pending_interaction_reason:
            return AgentLoopContinuationDecision(
                kind=CONTINUATION_WAIT,
                reason=facts.pending_interaction_reason,
            )
        if facts.guard_stop_reason:
            return AgentLoopContinuationDecision(
                kind=CONTINUATION_STOP,
                reason="guard_stop",
                message=facts.guard_stop_reason,
            )
        if facts.completion_signal:
            return AgentLoopContinuationDecision(
                kind=CONTINUATION_STOP,
                reason="completed",
                message="agent signaled completion",
                next_mode=facts.mode_name,
            )
        if facts.safety_limit_reached:
            return AgentLoopContinuationDecision(
                kind=CONTINUATION_STOP,
                reason="max_turns",
                message="reached loop safety limit without completion signal",
                metadata={
                    "loop_safety_limit": facts.safety_limit,
                    "turns_used": facts.turns_used,
                    "compatibility_reason": "max_turns",
                },
            )
        return AgentLoopContinuationDecision(kind=CONTINUATION_CONTINUE)
