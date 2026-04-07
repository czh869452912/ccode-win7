from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from embedagent.interaction import UserInputResponse
from embedagent.session import Session


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class ManagedSession(object):
    session: Session
    current_mode: str
    engine: Any = None
    status: str = "idle"
    workflow_state: str = "chat"
    active_plan_ref: str = ""
    current_command_context: str = ""
    current_command_turn_id: str = ""
    current_command_step_id: str = ""
    current_command_step_index: int = 0
    summary_ref: str = ""
    updated_at: str = field(default_factory=_utc_now)
    last_error: Optional[str] = None
    pending_permission: Optional[Any] = None
    pending_user_input: Optional[Any] = None
    pending_event: Optional[threading.Event] = None
    pending_result: Optional[bool] = None
    pending_user_event: Optional[threading.Event] = None
    pending_user_response: Optional[UserInputResponse] = None
    active_thread: Optional[threading.Thread] = None
    resume_summary: Optional[Dict[str, Any]] = None
    last_assistant_message: str = ""
    restore_stop_reason: str = ""
    restore_consumed_event_count: int = 0
    restore_transcript_event_count: int = 0
    current_phase: str = ""
    discipline_profile: str = ""
    current_activity: str = ""
    task_summary: str = ""
    task_items: List[Dict[str, Any]] = field(default_factory=list)
    remembered_permission_categories: Set[str] = field(default_factory=set)
    stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
