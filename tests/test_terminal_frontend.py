import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_protocol import CommandDescriptor, ShellDescriptor, SurfaceDescriptor
from prompt_toolkit.document import Document

from embedagent.frontend.tui.completion import TerminalCompleter
from embedagent.frontend.tui.shell_state import ShellState
from embedagent.frontend.tui.state import TerminalState

SHELL = ShellDescriptor(
    commands=[
        CommandDescriptor(
            id="custom.inspect",
            label="Inspect Target",
            group="custom",
            dispatch={"kind": "session.command", "command": "inspect"},
        )
    ],
    surfaces=[
        SurfaceDescriptor(
            id="custom.details",
            label="Details",
            placement="secondary",
            renderer_key="file_reference",
        )
    ],
)


class TestTerminalFrontendModules(unittest.TestCase):
    def setUp(self):
        self.state = TerminalState.from_shell_descriptor(
            workspace=tempfile.mkdtemp(),
            initial_mode="build",
            descriptor=SHELL,
        )
        self.state.contributions["custom.details"].data = {
            "items": [
                {"kind": "file", "path": "src/main.c"},
                {"kind": "file", "path": "docs/readme.md"},
            ]
        }
        self.state.session.session_items = [
            {"id": "sess-001", "current_mode": "build"},
        ]
        self.completer = TerminalCompleter(lambda: self.state)

    def _complete(self, text):
        document = Document(text=text, cursor_position=len(text))
        return [item.text for item in self.completer.get_completions(document, None)]

    def test_slash_completion(self):
        items = self._complete("/in")
        self.assertEqual(items, ["inspect"])

    def test_file_completion(self):
        items = self._complete("please open @src/")
        self.assertIn("src/main.c", items)

    def test_session_completion(self):
        items = self._complete("session:sess")
        self.assertIn("sess-001", items)

    def test_tui_shell_commands_and_contributions(self):
        from embedagent.frontend.tui.reducer import activate_contribution
        from embedagent.frontend.tui.shell_state import slash_commands

        shell = self.state.shell
        self.assertEqual([item.id for item in shell.commands], ["custom.inspect"])
        self.assertEqual([item.id for item in shell.surfaces], ["custom.details"])
        self.assertEqual(shell.command_by_id("custom.inspect").slash, "/inspect")
        self.assertEqual([item.slash for item in slash_commands(shell)], ["/inspect"])

        activate_contribution(self.state, "custom.details")
        self.assertEqual(self.state.overlay.active_id, "custom.details")
        self.assertIs(self.state.contributions["custom.details"].active, True)
        activate_contribution(self.state, "undeclared")
        self.assertEqual(self.state.overlay.active_id, "")
        self.assertIs(self.state.contributions["custom.details"].active, False)

    def test_empty_descriptor_has_no_registered_commands_or_surfaces(self):
        shell = ShellState(ShellDescriptor())

        self.assertEqual(shell.commands, ())
        self.assertEqual(shell.surfaces, ())

    def test_tui_command_palette_rendering_filters_commands(self):
        from embedagent.frontend.tui.views.command_palette import build_command_palette_text

        self.state.shell.command_palette.open = True
        self.state.shell.command_palette.query = "inspect"
        text = build_command_palette_text(self.state)
        self.assertIn("Inspect Target", text)
        self.assertIn("/inspect", text)
        self.assertNotIn("Open Tasks", text)


if __name__ == "__main__":
    unittest.main()
