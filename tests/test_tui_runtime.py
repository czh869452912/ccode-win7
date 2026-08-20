from __future__ import annotations

from pathlib import Path

from embedagent_protocol import (
    CapabilitySnapshot,
    CommandDescriptor,
    InteractionDescriptor,
    SessionBootstrap,
    SessionEventEnvelope,
    ShellDescriptor,
    SurfaceDescriptor,
    ThreadShell,
)

from embedagent.frontend.runtime import SessionClientRuntime
from embedagent.frontend.tui.controller import TerminalController
from embedagent.frontend.tui.frontend_adapter import TUIFrontend
from embedagent.frontend.tui.shell_state import visible_palette_commands
from embedagent.frontend.tui.state import TerminalState

ROOT = Path(__file__).resolve().parents[1]


def _thread(session_id="session-1", mode="build"):
    return ThreadShell(
        id=session_id,
        title="Session",
        archived=False,
        current_mode=mode,
        status="idle",
        updated_at="2026-08-13T00:00:00Z",
    )


def _bootstrap(session_id="session-1", mode="build"):
    return SessionBootstrap(
        schema_version=2,
        event_cursor=0,
        thread=_thread(session_id, mode),
        snapshot={
            "session_id": session_id,
            "current_mode": mode,
            "status": "idle",
        },
        activities=[{"kind": "assistant", "content": "Ready.", "status": "completed"}],
        capabilities=CapabilitySnapshot(),
    )


class FakeSessionPort(object):
    def __init__(self):
        self.submissions = []
        self.responses = []
        self.response_error = None
        self.closed = False

    def list_sessions(self, limit=10):
        return [_thread()][:limit]

    def get_session_bootstrap(self, reference, mode=""):
        return _bootstrap(reference, mode or "build")

    def get_session_capabilities(self, session_id=""):
        del session_id
        return CapabilitySnapshot()

    def create_session(self, mode):
        return _bootstrap(mode=mode)

    def resume_session(self, reference, mode):
        return _bootstrap("session-1" if reference == "latest" else reference, mode)

    def submit_user_message(self, session_id, text, stream):
        self.submissions.append((session_id, text, stream))

    def respond_to_interaction(self, session_id, interaction_id, payload):
        if self.response_error is not None:
            raise self.response_error
        self.responses.append((session_id, interaction_id, payload))
        return _bootstrap(session_id)

    def close(self):
        self.closed = True


class FakeWorkspacePort(object):
    def __init__(self):
        self.tree_calls = []

    def list_workspace_tree(self, path=".", max_depth=3, limit=200):
        self.tree_calls.append((path, max_depth, limit))
        return {"root": path, "items": [{"kind": "file", "path": "src/main.c"}]}


SHELL = ShellDescriptor(
    commands=[
        CommandDescriptor(
            id="workflow.inspect",
            label="Inspect",
            group="workflow",
            dispatch={"kind": "session.command", "command": "inspect"},
            availability={"visible_when": "has_session"},
        ),
        CommandDescriptor(
            id="workspace.files",
            label="Files",
            group="workspace",
            dispatch={"kind": "shell.surface", "surface_id": "workspace.files"},
            availability={"visible_when": "has_workspace"},
        ),
    ],
    surfaces=[
        SurfaceDescriptor(
            id="workspace.files",
            label="Files",
            placement="secondary",
            renderer_key="file_reference",
        )
    ],
    interactions=[
        InteractionDescriptor(kind="permission", renderer_key="interaction"),
        InteractionDescriptor(kind="user_input", renderer_key="interaction"),
    ],
)


class FakeOwner(object):
    def __init__(self, runtime, workspace_port):
        self.runtime = runtime
        self.workspace_port = workspace_port
        self.shell_descriptor = SHELL
        self.initial_mode = "build"
        self.resume_reference = ""
        self.initial_message = ""
        self.workspace = "."
        self.state = TerminalState.from_shell_descriptor(".", "build", SHELL)
        self.frontend = TUIFrontend(self)
        self.refresh_count = 0

    def refresh_views(self):
        self.refresh_count += 1


def _controller():
    runtime = SessionClientRuntime()
    session_port = FakeSessionPort()
    workspace_port = FakeWorkspacePort()
    runtime.bind_session_port(session_port)
    owner = FakeOwner(runtime, workspace_port)
    controller = TerminalController(owner)
    runtime.bind_dispatch(controller.on_runtime_action)
    return controller, owner, session_port, workspace_port


def test_tui_controller_consumes_runtime_actions_and_descriptor_commands():
    controller, owner, session_port, _workspace_port = _controller()

    controller.start()
    controller.handle_command("/inspect src/main.c")

    assert owner.state.session.current_session_id == "session-1"
    assert owner.state.timeline.items == ["assistant> Ready.", "user> /inspect src/main.c"]
    assert owner.state.session.session_items[0]["id"] == "session-1"
    assert session_port.submissions == [("session-1", "/inspect src/main.c", True)]


def test_tui_routes_workspace_surface_through_focused_workspace_port():
    controller, owner, _session_port, workspace_port = _controller()
    controller.start()

    controller.execute_shell_command("workspace.files")

    assert workspace_port.tree_calls == [(".", 3, 200)]
    assert owner.state.overlay.active_id == "workspace.files"
    assert owner.state.contributions["workspace.files"].data["items"][0]["path"] == ("src/main.c")


def test_tui_has_no_private_host_or_duplicate_session_runtime():
    tui_root = ROOT / "src/embedagent/frontend/tui"
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in tui_root.rglob("*.py")
        if path.name != "runtime.py"
    )

    assert not (tui_root / "runtime.py").exists()
    for forbidden in (
        ".adapter",
        "_event_cursor",
        "_generation",
        "_recovering",
    ):
        assert forbidden not in sources


def test_tui_normalizes_nested_interaction_and_uses_descriptor_response_shape():
    controller, owner, session_port, _workspace_port = _controller()
    controller.start()
    runtime = owner.runtime
    runtime.on_session_event(
        SessionEventEnvelope(
            2,
            "approval-1",
            "session-1",
            1,
            "approval.requested",
            "now",
            {
                "permission": {
                    "kind": "permission",
                    "interaction_id": "approval-1",
                    "reason": "Allow?",
                }
            },
        )
    )

    assert owner.state.session.pending_interaction["kind"] == "permission"
    controller.handle_input("2")

    assert session_port.responses == [("session-1", "approval-1", {"decision": "acceptForSession"})]


def test_tui_clears_pending_on_response_failed_and_renders_safe_failure():
    controller, owner, session_port, _workspace_port = _controller()
    controller.start()
    runtime = owner.runtime
    runtime.on_session_event(
        SessionEventEnvelope(
            2,
            "input-1",
            "session-1",
            1,
            "user-input.requested",
            "now",
            {
                "kind": "user_input",
                "interaction_id": "input-1",
                "question": "Target",
                "id": "target",
            },
        )
    )
    from embedagent_host.frontend_errors import FrontendPortError
    from embedagent_protocol import FailureRecord

    session_port.response_error = FrontendPortError(
        FailureRecord(
            code="provider_error",
            message="raw provider detail",
            safe_message="The provider request failed.",
            retryable=False,
            source="provider",
        )
    )
    controller.handle_input("custom")
    assert owner.state.session.pending_interaction["interaction_id"] == "input-1"
    assert owner.state.session.last_failure["code"] == "provider_error"

    runtime.on_session_event(
        SessionEventEnvelope(
            2,
            "input-1-failed",
            "session-1",
            2,
            "user-input.response.failed",
            "now",
            {"interaction_id": "input-1"},
        )
    )
    assert owner.state.session.pending_interaction is None


def test_tui_palette_filters_descriptor_commands_by_runtime_availability():
    _controller_instance, owner, _session_port, _workspace_port = _controller()
    commands = visible_palette_commands(
        owner.state.shell, availability=owner.state.command_availability()
    )
    assert [item.id for item in commands] == ["workspace.files"]
