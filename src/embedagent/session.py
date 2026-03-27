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
        self.turns.append(Turn(user_message=content))

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

    def api_messages(self) -> List[Dict[str, Any]]:
        return [message.to_api_dict() for message in self.messages]
