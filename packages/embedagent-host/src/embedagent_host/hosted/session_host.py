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

    def create_session(
        self, mode: str, event_handler: Optional[SessionEventHandler] = None
    ) -> Dict[str, object]:
        return self.adapter.create_session(mode, event_handler=event_handler)

    def resume_session(
        self, reference: str, mode: str, event_handler: Optional[SessionEventHandler] = None
    ) -> Dict[str, object]:
        return self.adapter.resume_session(reference, mode, event_handler=event_handler)

    def submit_user_message(
        self,
        session_id: str,
        text: str,
        stream: bool,
        wait: bool,
        permission_resolver=None,
        user_input_resolver=None,
        event_handler: Optional[SessionEventHandler] = None,
    ) -> None:
        self.adapter.submit_user_message(
            session_id=session_id,
            text=text,
            stream=stream,
            wait=wait,
            permission_resolver=permission_resolver,
            user_input_resolver=user_input_resolver,
            event_handler=event_handler,
        )
