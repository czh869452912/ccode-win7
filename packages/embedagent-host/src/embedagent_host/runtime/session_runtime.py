from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

from embedagent_core.session import Session


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class ManagedSession(object):
    session: Session
    current_mode: str
    agent_session: Any = None
    status: str = "idle"
    workflow_state: str = ""
    active_plan_ref: str = ""
    current_command_context: str = ""
    current_command_text: str = ""
    current_command_turn_id: str = ""
    current_command_step_id: str = ""
    current_command_step_index: int = 0
    summary_ref: str = ""
    updated_at: str = field(default_factory=_utc_now)
    last_error: Optional[str] = None
    pending_interaction: Optional[Any] = None
    pending_event: Optional[threading.Event] = None
    pending_response: Optional[Dict[str, Any]] = None
    active_thread: Optional[threading.Thread] = None
    active_thread_is_worker: bool = False
    resume_summary: Optional[Dict[str, Any]] = None
    last_assistant_message: str = ""
    restore_stop_reason: str = ""
    restore_consumed_event_count: int = 0
    restore_transcript_event_count: int = 0
    best_effort_restore_event_count: int = 0
    operation_diagnostics: Dict[str, Any] = field(default_factory=dict)
    runtime_config: Dict[str, Any] = field(default_factory=dict)
    compaction_state: Dict[str, Any] = field(default_factory=dict)
    recovery_state: Dict[str, Any] = field(default_factory=dict)
    turn_experience: Dict[str, Any] = field(default_factory=dict)
    remembered_permission_categories: Set[str] = field(default_factory=set)
    stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
