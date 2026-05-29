from __future__ import annotations

from typing import Any, Optional

from embedagent.harness.task_graph import TaskGraph


class HarnessSessionGraphState(object):
    """Session-scoped task graph store owned by the default C harness extension."""

    def __init__(self) -> None:
        self._graphs = {}  # type: Dict[str, TaskGraph]

    def get(self, session: Any) -> Optional[TaskGraph]:
        return self._graphs.get(self._key(session))

    def set(self, session: Any, graph: TaskGraph) -> TaskGraph:
        self._graphs[self._key(session)] = graph
        return graph

    def ensure_empty(self, session: Any) -> TaskGraph:
        graph = self.get(session)
        if graph is None:
            graph = TaskGraph.empty()
            self.set(session, graph)
        return graph

    def from_user_request(self, session: Any, user_text: str, mode_name: str) -> TaskGraph:
        graph = TaskGraph.from_user_request(user_text, mode_name)
        return self.set(session, graph)

    def _key(self, session: Any) -> str:
        session_id = str(getattr(session, "session_id", "") or "")
        if session_id:
            return session_id
        return str(id(session))
