from __future__ import annotations

from typing import Dict

from embedagent.project_memory import ProjectMemoryStore
from embedagent.session_store import SessionSummaryStore


class MemoryMaintenance(object):
    def __init__(
        self,
        summary_store: SessionSummaryStore,
        project_memory_store: ProjectMemoryStore,
        tool_result_store,
    ) -> None:
        self.summary_store = summary_store
        self.project_memory_store = project_memory_store
        self.tool_result_store = tool_result_store

    def run(self) -> Dict[str, object]:
        session_result = self.summary_store.cleanup()
        project_result = self.project_memory_store.cleanup()
        active_refs = set(self.summary_store.collect_stored_paths())
        active_refs.update(self.project_memory_store.collect_stored_paths())
        artifact_result = self.tool_result_store.cleanup_unreferenced(active_refs)
        return {
            'sessions': session_result,
            'project_memory': project_result,
            'artifacts': artifact_result,
        }
