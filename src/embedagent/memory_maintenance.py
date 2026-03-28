from __future__ import annotations

from typing import Dict, Optional

from embedagent.artifacts import ArtifactStore
from embedagent.project_memory import ProjectMemoryStore
from embedagent.session_store import SessionSummaryStore


class MemoryMaintenance(object):
    def __init__(
        self,
        artifact_store: ArtifactStore,
        summary_store: SessionSummaryStore,
        project_memory_store: ProjectMemoryStore,
    ) -> None:
        self.artifact_store = artifact_store
        self.summary_store = summary_store
        self.project_memory_store = project_memory_store

    def run(self) -> Dict[str, object]:
        session_result = self.summary_store.cleanup()
        project_result = self.project_memory_store.cleanup()
        active_refs = set(self.summary_store.collect_artifact_refs())
        active_refs.update(self.project_memory_store.collect_artifact_refs())
        artifact_result = self.artifact_store.cleanup(active_refs)
        return {
            'sessions': session_result,
            'project_memory': project_result,
            'artifacts': artifact_result,
        }
