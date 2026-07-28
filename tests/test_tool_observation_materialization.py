from __future__ import annotations

from embedagent_core.session import Action, Observation
from embedagent_host.runtime.projection_db import ProjectionDb
from embedagent_host.runtime.tool_commit import ToolCommitCoordinator
from embedagent_host.runtime.tool_result_store import ToolResultStore
from embedagent_host.runtime.transcript_store import TranscriptStore


def test_materialize_does_not_append_or_mutate_session_state(tmp_path):
    workspace = str(tmp_path)
    transcript_store = TranscriptStore(workspace)
    coordinator = ToolCommitCoordinator(
        ToolResultStore(workspace),
        ProjectionDb(str(tmp_path / ".embedagent" / "memory" / "projections.sqlite3")),
    )
    long_text = "x" * 5000

    prepared = coordinator.materialize(
        "session-1",
        Action("read_file", {"path": "a.txt"}, "call-1"),
        Observation("read_file", True, None, {"content": long_text}),
    )

    assert prepared.observation.data["content_stored_path"]
    assert prepared.replacements
    assert prepared.commit_token
    assert not transcript_store.transcript_exists("session-1")
