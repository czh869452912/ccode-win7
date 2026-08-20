from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from embedagent_protocol import CapabilitySnapshot, ShellDescriptor

from embedagent.frontend.tui.shell_state import ShellState


@dataclass
class CapabilityProfile:
    host_mode: str = "raw-console"
    ascii_only: bool = True
    low_color: bool = True
    allow_mouse: bool = False


@dataclass
class SessionState:
    current_session_id: str = ""
    current_mode: str = ""
    current_snapshot: Dict[str, Any] = field(default_factory=dict)
    session_items: List[Dict[str, Any]] = field(default_factory=list)
    session_selection: int = 0
    pending_interaction: Optional[Dict[str, Any]] = None
    last_failure: Optional[Dict[str, Any]] = None
    last_context_event: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TimelineState:
    items: List[str] = field(default_factory=list)
    stream_text: str = ""
    follow_output: bool = True


@dataclass
class ComposerState:
    prompt: str = "user> "


@dataclass
class StatusState:
    message: str = ""


@dataclass
class OverlayState:
    active_id: str = ""


@dataclass
class ContributionState:
    surface_id: str
    renderer_key: str
    label: str
    active: bool = False
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TerminalState:
    workspace: str
    initial_mode: str
    session_limit: int = 10
    transcript_limit: int = 240
    capability: CapabilityProfile = field(default_factory=CapabilityProfile)
    capabilities: CapabilitySnapshot = field(default_factory=CapabilitySnapshot)
    session: SessionState = field(default_factory=SessionState)
    timeline: TimelineState = field(default_factory=TimelineState)
    composer: ComposerState = field(default_factory=ComposerState)
    status: StatusState = field(default_factory=StatusState)
    overlay: OverlayState = field(default_factory=OverlayState)
    contributions: Dict[str, ContributionState] = field(default_factory=dict)
    shell: ShellState = field(default_factory=ShellState)

    @classmethod
    def from_shell_descriptor(
        cls, workspace: str, initial_mode: str, descriptor: ShellDescriptor, **kwargs: Any
    ) -> "TerminalState":
        if not isinstance(descriptor, ShellDescriptor):
            raise TypeError("descriptor must be a ShellDescriptor")
        contributions = {}
        for surface in descriptor.surfaces:
            if surface.placement != "secondary":
                continue
            contributions[surface.id] = ContributionState(
                surface_id=surface.id,
                renderer_key=surface.renderer_key,
                label=surface.label,
            )
        state = cls(
            workspace=workspace,
            initial_mode=initial_mode,
            shell=ShellState(descriptor),
            contributions=contributions,
            **kwargs,
        )
        state.session.current_mode = initial_mode
        return state

    def command_availability(self) -> Dict[str, object]:
        status = str(self.session.current_snapshot.get("status") or "")
        return {
            "has_session": bool(self.session.current_session_id),
            "has_workspace": bool(self.workspace),
            "running": status in ("running", "submitting"),
            "has_interaction": self.session.pending_interaction is not None,
        }
