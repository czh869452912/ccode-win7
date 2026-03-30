from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from embedagent.frontend.tui.models import ArtifactRow, EditorBuffer, ExplorerItem


@dataclass
class CapabilityProfile:
    host_mode: str = "raw-console"
    ascii_only: bool = True
    low_color: bool = True
    allow_mouse: bool = False


@dataclass
class SessionState:
    current_session_id: str = ""
    current_snapshot: Dict[str, Any] = field(default_factory=dict)
    session_items: List[Dict[str, Any]] = field(default_factory=list)
    session_selection: int = 0
    pending_permission: Optional[Dict[str, Any]] = None
    pending_user_input: Optional[Dict[str, Any]] = None
    last_error: str = ""
    last_context_event: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExplorerState:
    tab: str = "workspace"
    items: List[ExplorerItem] = field(default_factory=list)
    selection: int = 0
    root: str = "."


@dataclass
class TimelineState:
    lines: List[str] = field(default_factory=list)
    stream_text: str = ""
    follow_output: bool = True


@dataclass
class InspectorState:
    tab: str = "status"
    artifact_items: List[ArtifactRow] = field(default_factory=list)
    selected_artifact_ref: str = ""


@dataclass
class ComposerState:
    prompt: str = "user> "


@dataclass
class EditorState:
    buffer: EditorBuffer = field(default_factory=EditorBuffer)
    diff_preview: str = ""
    warning: str = ""


@dataclass
class TerminalState:
    workspace: str
    initial_mode: str
    session_limit: int = 10
    transcript_limit: int = 240
    capability: CapabilityProfile = field(default_factory=CapabilityProfile)
    session: SessionState = field(default_factory=SessionState)
    explorer: ExplorerState = field(default_factory=ExplorerState)
    timeline: TimelineState = field(default_factory=TimelineState)
    inspector: InspectorState = field(default_factory=InspectorState)
    composer: ComposerState = field(default_factory=ComposerState)
    editor: EditorState = field(default_factory=EditorState)
    workspace_snapshot: Dict[str, Any] = field(default_factory=dict)
    preview_path: str = ""
    preview_text: str = ""
    main_view: str = "timeline"
    help_text: str = ""
    status_message: str = ""
