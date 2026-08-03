import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_protocol import CommandDescriptor, ShellDescriptor, SurfaceDescriptor
from prompt_toolkit.document import Document

from embedagent.frontend.tui.completion import TerminalCompleter
from embedagent.frontend.tui.models import ExplorerItem
from embedagent.frontend.tui.state import TerminalState
from embedagent.frontend.tui.workbench import WorkbenchState

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
            renderer_key="generic_timeline",
        )
    ],
)


class TestTerminalFrontendModules(unittest.TestCase):
    def setUp(self):
        self.state = TerminalState(
            workspace=tempfile.mkdtemp(),
            initial_mode="build",
            workbench=WorkbenchState(SHELL),
        )
        self.state.explorer.items = [
            ExplorerItem(kind="file", path="src/main.c", label="[F] main.c"),
            ExplorerItem(kind="file", path="docs/readme.md", label="[F] readme.md"),
        ]
        self.state.session.session_items = [
            {"session_id": "sess-001", "current_mode": "build"},
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

    def test_tui_workbench_commands_and_surfaces(self):
        from embedagent.frontend.tui.workbench import (
            open_surface,
            slash_command_names,
        )

        workbench = self.state.workbench
        self.assertEqual([item.id for item in workbench.commands], ["custom.inspect"])
        self.assertEqual([item.id for item in workbench.surfaces], ["custom.details"])
        self.assertEqual(workbench.command_by_id("custom.inspect").slash, "/inspect")
        self.assertEqual([item.slash for item in slash_command_names(workbench)], ["/inspect"])

        next_state = open_surface(workbench, "custom.details")
        self.assertIsNot(next_state, workbench)
        self.assertEqual(next_state.active_surface, "custom.details")
        self.assertIs(next_state.right_panel_open, True)
        self.assertIs(open_surface(workbench, "undeclared"), workbench)

    def test_empty_descriptor_has_no_registered_commands_or_surfaces(self):
        workbench = WorkbenchState(ShellDescriptor())

        self.assertEqual(workbench.commands, ())
        self.assertEqual(workbench.surfaces, ())

    def test_tui_command_palette_rendering_filters_commands(self):
        from embedagent.frontend.tui.views.command_palette import build_command_palette_text

        self.state.workbench.command_palette.open = True
        self.state.workbench.command_palette.query = "inspect"
        text = build_command_palette_text(self.state)
        self.assertIn("Inspect Target", text)
        self.assertIn("/inspect", text)
        self.assertNotIn("Open Tasks", text)


if __name__ == "__main__":
    unittest.main()
