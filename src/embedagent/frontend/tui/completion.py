from __future__ import annotations

import re
from typing import Iterable, List

from prompt_toolkit.completion import Completer, Completion

from embedagent.frontend.tui.commands import command_names


class TerminalCompleter(Completer):
    def __init__(self, get_state) -> None:
        self.get_state = get_state

    def get_completions(self, document, complete_event):
        state = self.get_state()
        text_before = document.text_before_cursor
        stripped = text_before.lstrip()
        if stripped.startswith("/"):
            prefix = stripped[1:]
            for name in command_names(state.shell):
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
        for contribution in state.contributions.values():
            if contribution.renderer_key != "file_reference":
                continue
            for item in contribution.data.get("items") or []:
                if not isinstance(item, dict) or item.get("kind") != "file":
                    continue
                path = str(item.get("path") or "")
                if path and path not in seen:
                    seen.add(path)
                    values.append(path)
        return values[:200]

    def _session_candidates(self, state) -> Iterable[str]:
        for item in getattr(state.session, "session_items", []):
            if isinstance(item, dict):
                session_id = str(item.get("id") or "")
                if session_id:
                    yield session_id
