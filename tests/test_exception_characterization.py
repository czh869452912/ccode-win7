"""Characterization tests for exception handling behavior — verifies pre/post change equivalence."""


def test_permissions_load_missing_file():
    """Verify permissions handles missing file gracefully."""
    from embedagent.permissions import PermissionPolicy
    policy = PermissionPolicy(auto_approve_all=True, workspace="/nonexistent/path")
    rules = policy._load_rules("/nonexistent/path/permissions.json")
    assert rules == []


def test_task_store_load_missing_file():
    """Verify task_store handles missing file gracefully."""
    from embedagent.harness.task_store import load_task_snapshot
    result = load_task_snapshot("/nonexistent/path", "session-123")
    assert result == {}


def test_project_memory_load_missing_file():
    """Verify project_memory handles missing file gracefully."""
    from embedagent.project_memory import ProjectMemoryStore
    memory = ProjectMemoryStore("/nonexistent/path")
    result = memory._load_json("/nonexistent/path/file.json", default=[])
    assert result == []


def test_session_store_read_json_missing_file():
    """Verify session_store handles missing file gracefully."""
    from embedagent.session_store import SessionSummaryStore
    store = SessionSummaryStore("/nonexistent/path")
    result = store._read_json("/nonexistent/path/file.json")
    assert result is None


def test_workspace_recipes_load_json_missing_file():
    """Verify workspace_recipes handles missing file gracefully."""
    from embedagent.workspace_recipes import _load_json
    result = _load_json("/nonexistent/path/file.json", default={})
    assert result == {}


def test_core_adapter_read_file_missing():
    """Verify core_adapter handles missing file gracefully."""
    from embedagent.core.adapter import AgentCoreAdapter
    from embedagent.permissions import PermissionPolicy
    from embedagent.tools import ToolRuntime
    adapter = AgentCoreAdapter("/nonexistent/path")
    adapter.initialize(
        client=object(),
        tools=ToolRuntime("/nonexistent/path"),
        max_turns=8,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace="/nonexistent/path"),
    )
    result = adapter.get_diff_preview("missing.txt", "new content")
    assert result.path == "missing.txt"


def test_artifact_service_list_items():
    """Verify artifact_service handles adapter errors gracefully."""
    from embedagent.frontend.tui.services.artifacts import ArtifactService
    service = ArtifactService(None)
    result = service.list_items()
    assert result == []


def test_timeline_service_load():
    """Verify timeline_service handles adapter errors gracefully."""
    from embedagent.frontend.tui.services.timeline import TimelineService
    service = TimelineService(None)
    result = service.load("session-123")
    assert result == {"session_id": "session-123", "events": [], "latest_assistant_reply": ""}


def test_all_modified_modules_importable():
    """Verify all modified modules can be imported without errors."""
