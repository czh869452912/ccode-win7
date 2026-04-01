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
class Message:
    role: str
    content: str = ""
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    action_calls: List[Action] = field(default_factory=list)
    reasoning_content: str = ""

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


@dataclass
class Turn:
    user_message: str
    assistant_message: str = ""
    actions: List[Action] = field(default_factory=list)
    observations: List[Observation] = field(default_factory=list)
    steps: List["AgentStep"] = field(default_factory=list)
    message_start_index: int = 0
    message_end_index: int = 0


@dataclass
class AgentStep:
    step_id: str
    reasoning: str = ""
    assistant_message: str = ""
    actions: List[Action] = field(default_factory=list)
    observations: List[Observation] = field(default_factory=list)
    status: str = "in_progress"


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
    messages: List[Message] = field(default_factory=list)
    turns: List[Turn] = field(default_factory=list)

    def add_system_message(self, content: str) -> None:
        self.messages.append(Message(role="system", content=content))

    def add_user_message(self, content: str) -> None:
        self.messages.append(Message(role="user", content=content))
        index = len(self.messages) - 1
        self.turns.append(Turn(user_message=content, message_start_index=index, message_end_index=index))

    def add_assistant_reply(self, reply: AssistantReply) -> None:
        self.messages.append(
            Message(
                role="assistant",
                content=reply.content,
                action_calls=reply.actions,
                reasoning_content=reply.reasoning_content,
            )
        )
        if not self.turns:
            self.turns.append(Turn(user_message=""))
        self.turns[-1].assistant_message = reply.content
        self.turns[-1].actions.extend(reply.actions)
        self.turns[-1].message_end_index = len(self.messages) - 1

    def add_observation(self, action: Action, observation: Observation) -> None:
        self.messages.append(
            Message(
                role="tool",
                content=_to_json(observation.to_dict()),
                tool_call_id=action.call_id,
                name=action.name,
            )
        )
        if not self.turns:
            self.turns.append(Turn(user_message=""))
        self.turns[-1].observations.append(observation)
        self.turns[-1].message_end_index = len(self.messages) - 1

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
            stubbed += 1
        return stubbed
