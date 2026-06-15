import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prompt_toolkit.document import Document

from embedagent.frontend.tui.completion import TerminalCompleter
from embedagent.frontend.tui.models import ArtifactRow, ExplorerItem
from embedagent.frontend.tui.state import TerminalState


class TestTerminalFrontendModules(unittest.TestCase):
    def setUp(self):
        self.state = TerminalState(workspace=tempfile.mkdtemp(), initial_mode="build")
        self.state.explorer.items = [
            ExplorerItem(kind="file", path="src/main.c", label="[F] main.c"),
            ExplorerItem(kind="file", path="docs/readme.md", label="[F] readme.md"),
        ]
        self.state.inspector.artifact_items = [
            ArtifactRow(
                path=".embedagent/memory/artifacts/demo.json",
                tool_name="run_command",
                field_name="stdout",
            ),
        ]
        self.state.session.session_items = [
            {"session_id": "sess-001", "current_mode": "build"},
        ]
        self.completer = TerminalCompleter(lambda: self.state)

    def _complete(self, text):
        document = Document(text=text, cursor_position=len(text))
        return [item.text for item in self.completer.get_completions(document, None)]

    def test_slash_completion(self):
        items = self._complete("/he")
        self.assertIn("help", items)

    def test_file_completion(self):
        items = self._complete("please open @src/")
        self.assertIn("src/main.c", items)

    def test_artifact_completion(self):
        items = self._complete("artifact:.embed")
        self.assertIn(".embedagent/memory/artifacts/demo.json", items)

    def test_session_completion(self):
        items = self._complete("session:sess")
        self.assertIn("sess-001", items)

    def test_tui_workbench_commands_and_surfaces(self):
        from embedagent.frontend.tui.workbench import (
            RIGHT_PANEL_SURFACES,
            WorkbenchState,
            command_by_id,
            open_surface,
            slash_command_names,
        )

        self.assertIn("tasks", RIGHT_PANEL_SURFACES)
        self.assertIn("preview", RIGHT_PANEL_SURFACES)
        self.assertEqual(command_by_id("surface.tasks").slash, "/tasks")
        self.assertEqual(command_by_id("message.send").slash, "")
        self.assertNotIn("code", [item.slash.lstrip("/") for item in slash_command_names()])

        state = WorkbenchState()
        self.assertIs(state.right_panel_open, True)
        self.assertEqual(state.active_surface, "tasks")
        next_state = open_surface(state, "preview")
        self.assertIsNot(next_state, state)
        self.assertEqual(next_state.active_surface, "preview")
        self.assertIs(next_state.right_panel_open, True)

    def test_tui_slash_completion_uses_workbench_registry(self):
        from embedagent.frontend.tui.commands import command_names

        names = command_names()
        self.assertIn("tasks", names)
        self.assertIn("artifacts", names)
        self.assertIn("open", names)
        self.assertIn("edit", names)
        self.assertIn("save", names)
        self.assertNotIn("code", names)


if __name__ == "__main__":
    unittest.main()
