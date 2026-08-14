from __future__ import annotations

from pathlib import Path

from embedagent_protocol import (
    CapabilitySnapshot,
    CommandDescriptor,
    SessionBootstrap,
    ShellDescriptor,
    SurfaceDescriptor,
    ThreadShell,
)

from embedagent.frontend.runtime import SessionClientRuntime
from embedagent.frontend.tui.controller import TerminalController
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
        schema_version=1,
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
        del interaction_id, payload
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
        self.frontend = None
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
