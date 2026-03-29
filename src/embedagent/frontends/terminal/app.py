from __future__ import annotations

import os

from embedagent.frontends.terminal.controller import TerminalController
from embedagent.frontends.terminal.host import detect_host
from embedagent.frontends.terminal.layout import TerminalLayout
from embedagent.frontends.terminal.services import (
    ArtifactService,
    EditorService,
    SessionService,
    TimelineService,
    WorkspaceService,
)
from embedagent.frontends.terminal.state import TerminalState
from embedagent.frontends.terminal.theme import default_theme
from embedagent.frontends.terminal.views import (
    build_explorer_text,
    build_header_text,
    build_inspector_text,
    build_prompt,
    build_timeline_text,
)


class TerminalApp(object):
    def __init__(
        self,
        adapter,
        workspace: str,
        initial_mode: str,
        resume_reference: str = "",
        initial_message: str = "",
        session_limit: int = 10,
        transcript_limit: int = 240,
        headless = None,
        create_pipe_input=None,
        dummy_output=None,
    ) -> None:
        self.adapter = adapter
        self.workspace = workspace
        self.initial_mode = initial_mode
        self.resume_reference = resume_reference
        self.initial_message = (initial_message or "").strip()
        self.headless = bool(os.environ.get("EMBEDAGENT_TUI_HEADLESS", "").strip() == "1") if headless is None else bool(headless)
        self.create_pipe_input = create_pipe_input
        self.dummy_output = dummy_output
        self.state = TerminalState(
            workspace=workspace,
            initial_mode=initial_mode,
            session_limit=max(1, int(session_limit)),
            transcript_limit=max(40, int(transcript_limit)),
            capability=detect_host(),
        )
        self.theme = default_theme()
        self.session_service = SessionService(adapter, workspace, session_limit=self.state.session_limit)
        self.workspace_service = WorkspaceService(adapter, workspace)
        self.timeline_service = TimelineService(adapter)
        self.artifact_service = ArtifactService(adapter)
        self.editor_service = EditorService(self.workspace_service, workspace)
        self.pipe_input = None
        self._pipe_input_cm = None
        if self.headless and self.create_pipe_input is None:
            from embedagent.frontends.terminal.bootstrap import load_tui_dependencies

            deps = load_tui_dependencies()
            self.create_pipe_input = deps["create_pipe_input"]
            self.dummy_output = deps["DummyOutput"]()
        if self.headless and self.create_pipe_input is not None:
            self._pipe_input_cm = self.create_pipe_input()
            self.pipe_input = self._pipe_input_cm.__enter__()
        self.controller = TerminalController(self)
        self.layout = TerminalLayout(self)
        self.application = self.layout.application
        self.header = self.layout.header
        self.explorer_panel = self.layout.explorer
        self.transcript = self.layout.main
        self.editor_panel = self.layout.editor
        self.side_panel = self.layout.inspector
        self.composer = self.layout.composer

    @property
    def current_snapshot(self):
        return self.state.session.current_snapshot

    @property
    def current_session_id(self):
        return self.state.session.current_session_id

    @property
    def pending_permission(self):
        return self.state.session.pending_permission

    @property
    def transcript_lines(self):
        return self.state.timeline.lines

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
        self.explorer_panel.text = build_explorer_text(self.state)
        self.transcript.text = build_timeline_text(self.state)
        if self.state.timeline.follow_output and self.state.main_view != "editor":
            self.transcript.buffer.cursor_position = len(self.transcript.buffer.text)
        inspector_text = build_inspector_text(self.state, self.controller.current_summary, self.controller.latest_assistant_reply)
        self.side_panel.text = inspector_text
        self.composer.prompt = build_prompt(self.state)
        if self.state.main_view == "editor":
            if self.editor_panel.text != self.state.editor.buffer.content:
                self.editor_panel.text = self.state.editor.buffer.content
        self.application.invalidate()

    def _close_application_resources(self) -> None:
        if self._pipe_input_cm is None:
            return
        try:
            self._pipe_input_cm.__exit__(None, None, None)
        finally:
            self._pipe_input_cm = None
            self.pipe_input = None


