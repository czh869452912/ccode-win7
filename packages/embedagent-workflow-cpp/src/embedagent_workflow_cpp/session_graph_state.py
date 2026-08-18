from __future__ import annotations

import json
import threading
from typing import Any, Dict, Optional

from embedagent_workflow_cpp.task_graph import TaskGraph


class HarnessSessionGraphState(object):
    """Session-scoped task graph store owned by the default C harness extension."""

    def __init__(self) -> None:
        self._graphs = {}  # type: Dict[str, TaskGraph]
        self._fingerprints = {}  # type: Dict[str, str]
        self._lock = threading.RLock()

    def get(self, session: Any) -> Optional[TaskGraph]:
        key = self._key(session)
        workflow = self._workflow_projection(session)
        fingerprint = self._fingerprint(workflow)
        with self._lock:
            if not workflow:
                self._graphs.pop(key, None)
                self._fingerprints.pop(key, None)
                return None
            cached = self._graphs.get(key)
            if cached is not None and self._fingerprints.get(key) == fingerprint:
                return cached.clone()
            graph = TaskGraph.from_workflow_projection(workflow)
            if graph is None or graph.is_empty():
                self._graphs.pop(key, None)
                self._fingerprints.pop(key, None)
                return None
            self._graphs[key] = graph.clone()
            self._fingerprints[key] = fingerprint
            return graph.clone()

    def set(self, session: Any, graph: TaskGraph) -> TaskGraph:
        key = self._key(session)
        with self._lock:
            self._graphs[key] = graph.clone()
            self._fingerprints[key] = self._fingerprint(self._workflow_projection(session))
            return graph.clone()

    def ensure_empty(self, session: Any) -> TaskGraph:
        graph = self.get(session)
        if graph is None:
            graph = TaskGraph.empty()
        return graph

    def from_user_request(self, session: Any, user_text: str, mode_name: str) -> TaskGraph:
        graph = TaskGraph.from_user_request(user_text, mode_name)
        return graph

    def dispose(self, session: Any = None) -> None:
        with self._lock:
            if session is None:
                self._graphs.clear()
                self._fingerprints.clear()
                return
            key = self._key(session)
            self._graphs.pop(key, None)
            self._fingerprints.pop(key, None)

    def _workflow_projection(self, session: Any) -> Dict[str, Any]:
        state = getattr(session, "workflow_state", {})
        if not isinstance(state, dict):
            return {}
        workflow = state.get("workflow")
        return dict(workflow) if isinstance(workflow, dict) else {}

    def _fingerprint(self, workflow: Dict[str, Any]) -> str:
        return json.dumps(workflow or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _key(self, session: Any) -> str:
        session_id = str(getattr(session, "session_id", "") or "")
        if session_id:
            return session_id
        return str(id(session))
