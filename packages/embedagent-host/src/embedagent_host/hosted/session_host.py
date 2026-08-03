from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from embedagent_host.runtime.session_event_protocol import SessionEventHandler


@dataclass
class HostedSessionHost(object):
    adapter: Any

    def list_sessions(self, limit: int = 10) -> List[Dict[str, object]]:
        return self.adapter.list_sessions(limit=limit)

    def load_session_summary(self, reference: str) -> Dict[str, object]:
        return self.adapter.summary_store.load_summary(reference)

    def get_session_bootstrap(self, reference: str) -> Dict[str, object]:
        return self.adapter.get_session_bootstrap(reference)

    def create_session(
        self, mode: str, event_handler: Optional[SessionEventHandler] = None
    ) -> Dict[str, object]:
        return self.adapter.create_session(mode, event_handler=event_handler)

    def resume_session(
        self, reference: str, mode: str, event_handler: Optional[SessionEventHandler] = None
    ) -> Dict[str, object]:
        return self.adapter.resume_session(reference, mode, event_handler=event_handler)

    def set_session_mode(self, session_id: str, mode: str) -> Dict[str, object]:
        return self.adapter.set_session_mode(session_id, mode)

    def respond_to_interaction(
        self,
        session_id: str,
        interaction_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, object]:
        return self.adapter.respond_to_interaction(session_id, interaction_id, payload)

    def cancel_session(self, session_id: str) -> Dict[str, object]:
        return self.adapter.cancel_session(session_id)

    def submit_user_message(
        self,
        session_id: str,
        text: str,
        stream: bool,
        wait: bool,
        permission_resolver=None,
        user_input_resolver=None,
        event_handler: Optional[SessionEventHandler] = None,
    ) -> Dict[str, object]:
        return self.adapter.submit_user_message(
            session_id=session_id,
            text=text,
            stream=stream,
            wait=wait,
            permission_resolver=permission_resolver,
            user_input_resolver=user_input_resolver,
            event_handler=event_handler,
        )

    def list_tasks(self, session_id: str = "") -> Dict[str, object]:
        return self.adapter.list_tasks(session_id=session_id)

    def get_workspace_snapshot(self) -> Dict[str, object]:
        return self.adapter.get_workspace_snapshot()

    def list_workspace_tree(
        self,
        path: str = ".",
        max_depth: int = 3,
        limit: int = 200,
    ) -> Dict[str, object]:
        return self.adapter.list_workspace_tree(
            path=path,
            max_depth=max_depth,
            limit=limit,
        )

    def read_workspace_file(self, path: str) -> Dict[str, object]:
        return self.adapter.read_workspace_file(path)

    def write_workspace_file(self, path: str, content: str) -> Dict[str, object]:
        return self.adapter.write_workspace_file(path, content)
