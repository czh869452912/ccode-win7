from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


@dataclass
class Action:
    name: str
    arguments: Dict[str, Any]
    call_id: str
    raw_arguments: str = ""

    def to_api_dict(self) -> Dict[str, Any]:
        return {
            "id": self.call_id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": self.raw_arguments or _to_json(self.arguments),
            },
        }


@dataclass
class Observation:
    tool_name: str
    success: bool
    error: Optional[str]
    data: Any

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "error": self.error,
            "data": self.data,
        }


@dataclass
class AssistantReply:
    content: str
    actions: List[Action] = field(default_factory=list)
    finish_reason: Optional[str] = None
    reasoning_content: str = ""


@dataclass
class TranscriptMessage:
    role: str
    content: str = ""
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    action_calls: List[Action] = field(default_factory=list)
    reasoning_content: str = ""
    message_id: str = field(default_factory=lambda: "m-" + uuid.uuid4().hex[:12])
    turn_id: str = ""
    step_id: str = ""
    kind: str = "message"
    metadata: Dict[str, Any] = field(default_factory=dict)
    replaced_by_refs: List[str] = field(default_factory=list)
    archived: bool = False

    def to_api_dict(self) -> Dict[str, Any]:
        payload = {"role": self.role, "content": self.content}
        if self.name:
            payload["name"] = self.name
        if self.tool_call_id:
            payload["tool_call_id"] = self.tool_call_id
        if self.action_calls:
            payload["tool_calls"] = [
                action.to_api_dict() for action in self.action_calls
            ]
        if self.reasoning_content:
            payload["reasoning_content"] = self.reasoning_content
        return payload


Message = TranscriptMessage


@dataclass
class ToolCallRecord:
    call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    status: str = "pending"
    observation: Optional[Observation] = None
    started_at: str = field(default_factory=_utc_now)
    finished_at: str = ""
    progress: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Turn:
    user_message: str
    turn_id: str = field(default_factory=lambda: "t-" + uuid.uuid4().hex[:12])
    assistant_message: str = ""
    actions: List[Action] = field(default_factory=list)
    observations: List[Observation] = field(default_factory=list)
    steps: List["AgentStepState"] = field(default_factory=list)
    message_start_index: int = 0
    message_end_index: int = 0
    pending_interaction: Optional["PendingInteraction"] = None
    transitions: List["LoopTransition"] = field(default_factory=list)
    compact_boundaries: List["CompactBoundary"] = field(default_factory=list)


@dataclass
class AgentStepState:
    step_id: str
    step_index: int = 0
    reasoning: str = ""
    assistant_message: str = ""
    actions: List[Action] = field(default_factory=list)
    observations: List[Observation] = field(default_factory=list)
    tool_calls: List[ToolCallRecord] = field(default_factory=list)
    status: str = "in_progress"
    transition: Optional["LoopTransition"] = None


AgentStep = AgentStepState


@dataclass
class CompactBoundary:
    boundary_id: str = field(default_factory=lambda: "cb-" + uuid.uuid4().hex[:12])
    summary_text: str = ""
    compacted_turn_count: int = 0
    created_at: str = field(default_factory=_utc_now)
    mode_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PendingInteraction:
    interaction_id: str = field(default_factory=lambda: "pi-" + uuid.uuid4().hex[:12])
    kind: str = ""
    tool_name: str = ""
    request_payload: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now)
    status: str = "pending"
    resolution_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoopTransition:
    reason: str
    message: str = ""
    pending_interaction: Optional[PendingInteraction] = None
    next_mode: str = ""
    turns_used: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextAssemblyResult:
    messages: List[Dict[str, Any]]
    used_chars: int
    approx_tokens: int
    compacted: bool
    summarized_turns: int
    recent_turns: int
    policy: Any
    budget: Any
    stats: Any
    summary_message: str = ""
    intelligence_sections: List[Dict[str, Any]] = field(default_factory=list)
    analysis: Dict[str, Any] = field(default_factory=dict)
    replacements: List[Dict[str, Any]] = field(default_factory=list)
    pipeline_steps: List[str] = field(default_factory=list)


@dataclass
class QueryTurnResult:
    final_text: str
    session: "Session"
    transition: LoopTransition
    turns_used: int = 0
    pending_interaction: Optional[PendingInteraction] = None


@dataclass
class LoopResult:
    """Structured result returned by AgentLoop.run().

    Replaces the previous bare ``Tuple[str, Session]`` + RuntimeError pattern.
    Callers can branch on ``termination_reason`` without parsing exception text.

    Possible ``termination_reason`` values
    ---------------------------------------
    ``"completed"``   — agent replied without requesting more tool calls.
    ``"max_turns"``   — hit the ``max_turns`` ceiling.
    ``"guard"``       — LoopGuard stopped the loop (doom-loop protection).
    ``"cancelled"``   — external ``stop_event`` was set.
    ``"error"``       — unexpected exception; ``error`` field contains the message.
    """

    final_text: str
    session: "Session"
    termination_reason: str  # completed | max_turns | guard | cancelled | error
    error: Optional[str] = None
    turns_used: int = 0


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started_at: str = field(default_factory=_utc_now)
    messages: List[TranscriptMessage] = field(default_factory=list)
    turns: List[Turn] = field(default_factory=list)
    compact_boundaries: List[CompactBoundary] = field(default_factory=list)
    pending_interaction: Optional[PendingInteraction] = None

    def add_system_message(
        self,
        content: str,
        message_id: str = "",
        turn_id: str = "",
        step_id: str = "",
        kind: str = "message",
        metadata: Optional[Dict[str, Any]] = None,
        replaced_by_refs: Optional[List[str]] = None,
    ) -> TranscriptMessage:
        turn_value = turn_id or (self.turns[-1].turn_id if self.turns else "")
        message = TranscriptMessage(
            role="system",
            content=content,
            message_id=message_id or ("m-" + uuid.uuid4().hex[:12]),
            turn_id=turn_value,
            step_id=step_id or self._current_step_id(),
            kind=kind,
            metadata=dict(metadata or {}),
            replaced_by_refs=list(replaced_by_refs or []),
        )
        self.messages.append(message)
        return message

    def add_user_message(self, content: str, turn_id: str = "", message_id: str = "") -> Turn:
        turn = Turn(
            user_message=content,
            turn_id=turn_id or ("t-" + uuid.uuid4().hex[:12]),
        )
        self.messages.append(
            TranscriptMessage(
                role="user",
                content=content,
                message_id=message_id or ("m-" + uuid.uuid4().hex[:12]),
                turn_id=turn.turn_id,
            )
        )
        index = len(self.messages) - 1
        turn.message_start_index = index
        turn.message_end_index = index
        self.turns.append(turn)
        return turn

    def begin_step(self, reasoning: str = "", step_id: str = "") -> AgentStepState:
        if not self.turns:
            self.turns.append(Turn(user_message=""))
        turn = self.turns[-1]
        step = AgentStepState(
            step_id=step_id or ("s-" + uuid.uuid4().hex[:12]),
            step_index=len(turn.steps) + 1,
            reasoning=reasoning,
        )
        turn.steps.append(step)
        return step

    def current_step(self) -> Optional[AgentStepState]:
        if not self.turns or not self.turns[-1].steps:
            return None
        return self.turns[-1].steps[-1]

    def record_tool_call(self, action: Action) -> ToolCallRecord:
        step = self.current_step() or self.begin_step()
        record = ToolCallRecord(
            call_id=action.call_id,
            tool_name=action.name,
            arguments=dict(action.arguments),
            status="started",
        )
        step.tool_calls.append(record)
        step.actions.append(action)
        return record

    def add_assistant_reply(
        self,
        reply: AssistantReply,
        message_id: str = "",
        turn_id: str = "",
        step_id: str = "",
    ) -> None:
        step = self.current_step()
        if step is None:
            step = self.begin_step(reasoning=reply.reasoning_content, step_id=step_id)
        else:
            if reply.reasoning_content:
                step.reasoning = reply.reasoning_content
        self.messages.append(
            TranscriptMessage(
                role="assistant",
                content=reply.content,
                action_calls=reply.actions,
                reasoning_content=reply.reasoning_content,
                message_id=message_id or ("m-" + uuid.uuid4().hex[:12]),
                turn_id=turn_id or (self.turns[-1].turn_id if self.turns else ""),
                step_id=step_id or (step.step_id if step is not None else ""),
            )
        )
        if not self.turns:
            self.turns.append(Turn(user_message=""))
        self.turns[-1].assistant_message = reply.content
        self.turns[-1].actions.extend(reply.actions)
        step.assistant_message = reply.content
        if reply.reasoning_content:
            step.reasoning = reply.reasoning_content
        step.status = "assistant_reply"
        self.turns[-1].message_end_index = len(self.messages) - 1
        for action in reply.actions:
            existing = self._find_tool_call(action.call_id)
            if existing is None:
                self.record_tool_call(action)

    def add_observation(
        self,
        action: Action,
        observation: Observation,
        message_id: str = "",
        turn_id: str = "",
        step_id: str = "",
        finished_at: str = "",
        replaced_by_refs: Optional[List[str]] = None,
    ) -> None:
        record = self._find_tool_call(action.call_id)
        if record is None:
            record = self.record_tool_call(action)
        record.status = "completed"
        record.observation = observation
        record.finished_at = finished_at or _utc_now()
        self.messages.append(
            TranscriptMessage(
                role="tool",
                content=_to_json(observation.to_dict()),
                tool_call_id=action.call_id,
                name=action.name,
                message_id=message_id or ("m-" + uuid.uuid4().hex[:12]),
                turn_id=turn_id or (self.turns[-1].turn_id if self.turns else ""),
                step_id=step_id or self._current_step_id(),
                kind="tool_result",
                replaced_by_refs=list(replaced_by_refs or self._artifact_refs_from_observation(observation)),
            )
        )
        if not self.turns:
            self.turns.append(Turn(user_message=""))
        self.turns[-1].observations.append(observation)
        step = self.current_step()
        if step is not None:
            step.observations.append(observation)
            step.status = "tool_result"
        self.turns[-1].message_end_index = len(self.messages) - 1

    def record_transition(self, transition: LoopTransition) -> None:
        if not self.turns:
            self.turns.append(Turn(user_message=""))
        self.turns[-1].transitions.append(transition)
        step = self.current_step()
        if step is not None:
            step.transition = transition
            if transition.reason in ("completed", "aborted", "guard_stop", "max_turns"):
                step.status = transition.reason
        if transition.pending_interaction is not None:
            self.pending_interaction = transition.pending_interaction
            self.turns[-1].pending_interaction = transition.pending_interaction
        elif transition.reason == "completed":
            self.pending_interaction = None
            self.turns[-1].pending_interaction = None

    def resolve_pending_interaction(self, resolution_payload: Dict[str, Any]) -> Optional[PendingInteraction]:
        pending = self.pending_interaction
        if pending is None:
            return None
        pending.status = "resolved"
        pending.resolution_payload = dict(resolution_payload)
        self.pending_interaction = None
        if self.turns:
            self.turns[-1].pending_interaction = None
        return pending

    def add_compact_boundary(
        self,
        summary_text: str,
        compacted_turn_count: int,
        mode_name: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        boundary_id: str = "",
        created_at: str = "",
    ) -> CompactBoundary:
        boundary = CompactBoundary(
            boundary_id=boundary_id or ("cb-" + uuid.uuid4().hex[:12]),
            summary_text=summary_text,
            compacted_turn_count=max(0, int(compacted_turn_count)),
            created_at=created_at or _utc_now(),
            mode_name=mode_name,
            metadata=dict(metadata or {}),
        )
        self.compact_boundaries.append(boundary)
        if self.turns:
            self.turns[-1].compact_boundaries.append(boundary)
        self.add_system_message(
            summary_text,
            turn_id=self.turns[-1].turn_id if self.turns else "",
            step_id=self._current_step_id(),
            kind="compact_boundary",
            metadata={
                "boundary_id": boundary.boundary_id,
                "compacted_turn_count": boundary.compacted_turn_count,
                "mode_name": boundary.mode_name,
            },
        )
        if self.turns:
            self.turns[-1].message_end_index = len(self.messages) - 1
        return boundary

    def latest_compact_boundary(self) -> Optional[CompactBoundary]:
        if not self.compact_boundaries:
            return None
        return self.compact_boundaries[-1]

    def api_messages(self) -> List[Dict[str, Any]]:
        return [message.to_api_dict() for message in self.messages]

    def trim_old_observations(self, keep_turns: int = 20) -> int:
        """Replace observation content in turns older than *keep_turns* with a stub.

        This bounds in-memory growth for long sessions without losing the
        message list structure that ``ContextManager`` relies on.  The stub
        preserves ``success``, ``tool_name``, and ``error`` so that summaries
        and the guard system still work correctly.

        Returns the number of messages whose content was stubbed.
        """
        if len(self.turns) <= keep_turns:
            return 0
        archived_turns = self.turns[:-keep_turns]
        archived_indices: set = set()
        for turn in archived_turns:
            # Collect indices of tool-result messages for this turn.
            for idx in range(turn.message_start_index, turn.message_end_index + 1):
                if idx < len(self.messages) and self.messages[idx].role == "tool":
                    archived_indices.add(idx)
        stubbed = 0
        for idx in archived_indices:
            msg = self.messages[idx]
            try:
                data = json.loads(msg.content)
            except (ValueError, TypeError):
                continue
            if not isinstance(data, dict) or data.get("_archived"):
                continue
            stub = {
                "_archived": True,
                "success": data.get("success"),
                "error": data.get("error"),
                "data": {"tool_name": data.get("data", {}).get("tool_name") if isinstance(data.get("data"), dict) else None},
            }
            msg.content = _to_json(stub)
            msg.archived = True
            stubbed += 1
        return stubbed

    def _current_step_id(self) -> str:
        step = self.current_step()
        return step.step_id if step is not None else ""

    def _find_tool_call(self, call_id: str) -> Optional[ToolCallRecord]:
        for turn in reversed(self.turns):
            for step in reversed(turn.steps):
                for record in reversed(step.tool_calls):
                    if record.call_id == call_id:
                        return record
        return None

    def _artifact_refs_from_observation(self, observation: Observation) -> List[str]:
        if not isinstance(observation.data, dict):
            return []
        refs = []
        for key, value in observation.data.items():
            if key.endswith("_artifact_ref") and value:
                refs.append(str(value))
        return refs[:8]
