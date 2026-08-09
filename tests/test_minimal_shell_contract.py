from embedagent_protocol import ShellDescriptor, SurfaceDescriptor

from embedagent.frontend.tui.state import TerminalState


def minimal_descriptor():
    return ShellDescriptor()


def test_tui_core_state_has_no_required_auxiliary_features():
    state = TerminalState.from_shell_descriptor(
        workspace="C:/workspace",
        initial_mode="explore",
        descriptor=minimal_descriptor(),
    )

    assert state.session.current_mode == "explore"
    assert state.timeline.items == []
    assert state.overlay.active_id == ""
    assert state.contributions == {}
    for retired_field in (
        "explorer",
        "editor",
        "inspector",
        "terminal",
        "source_control",
        "tasks",
        "preview_path",
        "workspace_snapshot",
        "workbench",
    ):
        assert not hasattr(state, retired_field)


def test_tui_initializes_only_registered_secondary_contributions():
    descriptor = ShellDescriptor(
        surfaces=[
            SurfaceDescriptor(
                id="commands",
                label="Commands",
                placement="overlay",
                renderer_key="command_palette",
            ),
            SurfaceDescriptor(
                id="terminal",
                label="Terminal",
                placement="secondary",
                renderer_key="terminal",
            ),
        ]
    )

    state = TerminalState.from_shell_descriptor(
        workspace="C:/workspace",
        initial_mode="build",
        descriptor=descriptor,
    )

    assert list(state.contributions) == ["terminal"]
    assert state.contributions["terminal"].renderer_key == "terminal"
