from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Protocol

from embedagent_core.session import AssistantReply


class ModelClientError(Exception):
    pass


class ModelClient(Protocol):
    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AssistantReply:
        raise NotImplementedError

    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        on_text_delta: Optional[Callable[[str], None]] = None,
        on_reasoning_delta: Optional[Callable[[str], None]] = None,
    ) -> AssistantReply:
        raise NotImplementedError
