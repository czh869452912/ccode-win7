from __future__ import annotations

import re
from typing import Iterable, List, Set

from prompt_toolkit.completion import Completer, Completion

from embedagent.frontends.terminal.commands import command_names


class TerminalCompleter(Completer):
    def __init__(self, get_state) -> None:
        self.get_state = get_state

    def get_completions(self, document, complete_event):
        state = self.get_state()
        text_before = document.text_before_cursor
        stripped = text_before.lstrip()
        if stripped.startswith("/"):
            prefix = stripped[1:]
            for name in command_names():
                if prefix and not name.startswith(prefix):
                    continue
                yield Completion(name, start_position=-len(prefix), display="/" + name)
            return
        file_match = re.search(r"@([^\s]*)$", text_before)
        if file_match:
            prefix = file_match.group(1)
            for candidate in self._file_candidates(state):
                if prefix and prefix.lower() not in candidate.lower():
                    continue
                yield Completion(candidate, start_position=-len(prefix), display="@" + candidate)
            return
        artifact_match = re.search(r"artifact:([^\s]*)$", text_before)
        if artifact_match:
            prefix = artifact_match.group(1)
            for item in self._artifact_candidates(state):
                if prefix and prefix.lower() not in item.lower():
                    continue
                yield Completion(item, start_position=-len(prefix), display="artifact:" + item)
            return
        session_match = re.search(r"session:([^\s]*)$", text_before)
        if session_match:
            prefix = session_match.group(1)
            for item in self._session_candidates(state):
                if prefix and prefix.lower() not in item.lower():
                    continue
                yield Completion(item, start_position=-len(prefix), display="session:" + item)

    def _file_candidates(self, state) -> List[str]:
        values = []  # type: List[str]
        seen = set()  # type: Set[str]
        for item in getattr(state.explorer, 'items', []):
            path = getattr(item, 'path', '')
            if path and path not in seen:
                seen.add(path)
                values.append(path)
        if state.preview_path and state.preview_path not in seen:
            seen.add(state.preview_path)
            values.append(state.preview_path)
        editor_path = getattr(getattr(state.editor, 'buffer', None), 'path', '')
        if editor_path and editor_path not in seen:
            seen.add(editor_path)
            values.append(editor_path)
        summary = getattr(getattr(state.session, 'current_snapshot', {}), 'get', None)
        if callable(summary):
            pass
        return values[:200]

    def _artifact_candidates(self, state) -> Iterable[str]:
        for item in getattr(state.inspector, 'artifact_items', []):
            path = getattr(item, 'path', '')
            if path:
                yield path

    def _session_candidates(self, state) -> Iterable[str]:
        for item in getattr(state.session, 'session_items', []):
            if isinstance(item, dict):
                session_id = str(item.get('session_id') or '')
                if session_id:
                    yield session_id
