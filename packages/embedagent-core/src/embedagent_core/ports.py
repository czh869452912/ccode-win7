from __future__ import annotations

from typing import Any, List, Optional, Protocol

from embedagent_core.session import ContextAssemblyResult
from embedagent_core.session_view import SessionReadView


class ContextAssemblerPort(Protocol):
    reducers: Any

    def initial_system_messages(
        self, session: SessionReadView, mode_name: str, workflow_state: str = ""
    ) -> List[str]:
        raise NotImplementedError

    def build_messages(
        self,
        session: SessionReadView,
        mode_name: str,
        tools: Any = None,
        workflow_state: str = "",
        force_compact: bool = False,
    ) -> ContextAssemblyResult:
        raise NotImplementedError


class SessionRestorePolicyPort(Protocol):
    def trusted_event_count(self, session_id: str) -> int:
        raise NotImplementedError


class StrictSessionRestorePolicy(object):
    def trusted_event_count(self, session_id: str) -> int:
        del session_id
        return 0


class SessionProjectionPort(Protocol):
    def refresh(
        self,
        session: SessionReadView,
        current_mode: str,
        assembly: Optional[ContextAssemblyResult] = None,
    ) -> None:
        raise NotImplementedError


class NoopContextAssembler(object):
    reducers = {}

    def initial_system_messages(
        self, session: SessionReadView, mode_name: str, workflow_state: str = ""
    ) -> List[str]:
        del session, mode_name, workflow_state
        return []

    def build_messages(
        self,
        session: SessionReadView,
        mode_name: str,
        tools: Any = None,
        workflow_state: str = "",
        force_compact: bool = False,
    ) -> ContextAssemblyResult:
        del mode_name, tools, workflow_state, force_compact
        messages = [message.to_api_dict() for message in list(session.messages or [])]
        return ContextAssemblyResult(
            messages=messages,
            used_chars=sum(len(str(item.get("content") or "")) for item in messages),
            approx_tokens=0,
            compacted=False,
            summarized_turns=0,
            recent_turns=len(session.turns or []),
            policy=None,
            budget=None,
            stats=None,
        )


class NoopSessionProjection(object):
    def refresh(
        self,
        session: SessionReadView,
        current_mode: str,
        assembly: Optional[ContextAssemblyResult] = None,
    ) -> None:
        del session, current_mode, assembly
