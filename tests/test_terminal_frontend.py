import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from prompt_toolkit.document import Document

from embedagent.frontends.terminal.completion import TerminalCompleter
from embedagent.frontends.terminal.models import ArtifactRow, ExplorerItem
from embedagent.frontends.terminal.state import TerminalState


class TestTerminalFrontendModules(unittest.TestCase):
    def setUp(self):
        self.state = TerminalState(workspace=tempfile.mkdtemp(), initial_mode='code')
        self.state.explorer.items = [
            ExplorerItem(kind='file', path='src/main.c', label='[F] main.c'),
            ExplorerItem(kind='file', path='docs/readme.md', label='[F] readme.md'),
        ]
        self.state.inspector.artifact_items = [
            ArtifactRow(path='.embedagent/memory/artifacts/demo.json', tool_name='run_command', field_name='stdout'),
        ]
        self.state.session.session_items = [
            {'session_id': 'sess-001', 'current_mode': 'code'},
        ]
        self.completer = TerminalCompleter(lambda: self.state)

    def _complete(self, text):
        document = Document(text=text, cursor_position=len(text))
        return [item.text for item in self.completer.get_completions(document, None)]

    def test_slash_completion(self):
        items = self._complete('/he')
        self.assertIn('help', items)

    def test_file_completion(self):
        items = self._complete('please open @src/')
        self.assertIn('src/main.c', items)

    def test_artifact_completion(self):
        items = self._complete('artifact:.embed')
        self.assertIn('.embedagent/memory/artifacts/demo.json', items)

    def test_session_completion(self):
        items = self._complete('session:sess')
        self.assertIn('sess-001', items)


if __name__ == '__main__':
    unittest.main()
