from __future__ import annotations

import os

from embedagent.frontend.tui.contributions import render_contribution
from embedagent.frontend.tui.controller import TerminalController
from embedagent.frontend.tui.frontend_adapter import TUIFrontend
from embedagent.frontend.tui.host import detect_host
from embedagent.frontend.tui.layout import TerminalLayout
from embedagent.frontend.tui.state import TerminalState
from embedagent.frontend.tui.theme import default_theme
from embedagent.frontend.tui.views import (
    build_command_palette_text,
    build_header_text,
    build_prompt,
    build_timeline_text,
)


class TerminalApp(object):
    def __init__(
        self,
        runtime,
        workspace: str,
        initial_mode: str,
        resume_reference: str = "",
        initial_message: str = "",
        session_limit: int = 10,
        transcript_limit: int = 240,
        headless=None,
        create_pipe_input=None,
        dummy_output=None,
    ) -> None:
        self.runtime = runtime
        self.workspace = workspace
        self.initial_mode = initial_mode
        self.resume_reference = resume_reference
        self.initial_message = (initial_message or "").strip()
        self.headless = (
            bool(os.environ.get("EMBEDAGENT_TUI_HEADLESS", "").strip() == "1")
            if headless is None
            else bool(headless)
        )
        self.create_pipe_input = create_pipe_input
        self.dummy_output = dummy_output
        self.state = TerminalState.from_shell_descriptor(
            workspace=workspace,
            initial_mode=initial_mode,
            descriptor=runtime.shell_descriptor,
            session_limit=max(1, int(session_limit)),
            transcript_limit=max(40, int(transcript_limit)),
            capability=detect_host(),
        )
        self.theme = default_theme()
        self.pipe_input = None
        self._pipe_input_cm = None
        if self.headless and self.create_pipe_input is None:
            from embedagent.frontend.tui.bootstrap import load_tui_dependencies

            deps = load_tui_dependencies()
            self.create_pipe_input = deps["create_pipe_input"]
            self.dummy_output = deps["DummyOutput"]()
        if self.headless and self.create_pipe_input is not None:
            self._pipe_input_cm = self.create_pipe_input()
            self.pipe_input = self._pipe_input_cm.__enter__()
        self.frontend = TUIFrontend(self)
        self.controller = TerminalController(self)
        self.layout = TerminalLayout(self)
        self.application = self.layout.application
        self.header = self.layout.header
        self.transcript = self.layout.main
        self.composer = self.layout.composer
        self.status = self.layout.status

    @property
    def current_snapshot(self):
        return self.state.session.current_snapshot

    @property
    def current_session_id(self):
        return self.state.session.current_session_id

    @property
    def pending_interaction(self):
        return self.state.session.pending_interaction

    @property
    def transcript_lines(self):
        return self.state.timeline.items

    @property
    def last_context_event(self):
        return self.state.session.last_context_event

    @property
    def last_error(self):
        return self.state.session.last_error

    def run(self) -> int:
        try:
            self.controller.start()
            self.refresh_views()
            self.application.run()
            return 0
        finally:
            self._close_application_resources()

    def refresh_views(self) -> None:
        self.header.text = build_header_text(self.state)
        self.transcript.text = build_timeline_text(self.state)
        if self.state.timeline.follow_output:
            self.transcript.buffer.cursor_position = len(self.transcript.buffer.text)
        self.composer.prompt = build_prompt(self.state)
        self.layout.command_palette.text = build_command_palette_text(self.state)
        active_id = self.state.overlay.active_id
        contribution = self.state.contributions.get(active_id)
        self.layout.contribution.text = (
            render_contribution(contribution) if contribution is not None else ""
        )
        snapshot = self.state.session.current_snapshot
        self.status.text = "mode=%s  status=%s  session=%s" % (
            self.state.session.current_mode or self.initial_mode,
            snapshot.get("status") or "idle",
            self.state.session.current_session_id[:12] or "-",
        )
        self.application.invalidate()

    def _close_application_resources(self) -> None:
        self.runtime.close()
        if self._pipe_input_cm is None:
            return
        try:
            self._pipe_input_cm.__exit__(None, None, None)
        finally:
            self._pipe_input_cm = None
            self.pipe_input = None
