from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from embedagent_protocol.app_protocol import (
    CapabilitySnapshot,
    SessionBootstrap,
    ThreadShell,
)
from embedagent_protocol.session_events import SessionEventEnvelope


class SessionEventSink(ABC):
    @abstractmethod
    def on_session_event(self, envelope: SessionEventEnvelope) -> None:
        raise NotImplementedError


class FrontendSessionPort(ABC):
    @abstractmethod
    def list_sessions(self, limit: int = 10) -> List[ThreadShell]:
        raise NotImplementedError

    @abstractmethod
    def load_session_summary(self, reference: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_session_bootstrap(self, reference: str, mode: str = "") -> SessionBootstrap:
        raise NotImplementedError

    @abstractmethod
    def get_session_capabilities(self, session_id: str = "") -> CapabilitySnapshot:
        raise NotImplementedError

    @abstractmethod
    def create_session(self, mode: str) -> SessionBootstrap:
        raise NotImplementedError

    @abstractmethod
    def resume_session(self, reference: str, mode: str) -> SessionBootstrap:
        raise NotImplementedError

    @abstractmethod
    def submit_user_message(self, session_id: str, text: str, stream: bool) -> None:
        raise NotImplementedError

    @abstractmethod
    def cancel_session(self, session_id: str) -> SessionBootstrap:
        raise NotImplementedError

    @abstractmethod
    def set_session_mode(self, session_id: str, mode: str) -> SessionBootstrap:
        raise NotImplementedError

    @abstractmethod
    def respond_to_interaction(
        self,
        session_id: str,
        interaction_id: str,
        payload: Dict[str, Any],
    ) -> SessionBootstrap:
        raise NotImplementedError

    @abstractmethod
    def rename_session(self, session_id: str, title: str) -> ThreadShell:
        raise NotImplementedError

    @abstractmethod
    def archive_session(self, session_id: str) -> ThreadShell:
        raise NotImplementedError

    @abstractmethod
    def fork_session(self, session_id: str, title: str = "") -> ThreadShell:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError


class FrontendWorkspacePort(ABC):
    @abstractmethod
    def get_workspace_snapshot(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_workspace_tree(
        self,
        path: str = ".",
        max_depth: int = 3,
        limit: int = 200,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_file_children(self, path: str = ".", limit: int = 200) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def read_file(self, path: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_diff_preview(self, path: str, new_content: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def reload_resources(self, session_id: str = "", reason: str = "api") -> Dict[str, Any]:
        raise NotImplementedError
