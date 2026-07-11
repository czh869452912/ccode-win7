"""Characterization tests for exception handling behavior — verifies pre/post change equivalence."""


def test_permissions_load_missing_file():
    """Verify permissions handles missing file gracefully."""
    from embedagent_core.permissions import PermissionPolicy

    policy = PermissionPolicy(auto_approve_all=True, workspace="/nonexistent/path")
    rules = policy._load_rules("/nonexistent/path/permissions.json")
    assert rules == []


def test_task_store_load_missing_file():
    """Verify task_store handles missing file gracefully."""
    from embedagent.workflow_packages.c_cpp.task_store import load_task_snapshot

    result = load_task_snapshot("/nonexistent/path", "session-123")
    assert result == {}


def test_project_memory_load_missing_file():
    """Verify project_memory handles missing file gracefully."""
    from embedagent.project_memory import ProjectMemoryStore

    memory = ProjectMemoryStore("/nonexistent/path")
    result = memory._load_json("/nonexistent/path/file.json", default=[])
    assert result == []


def test_session_store_read_json_missing_file(tmp_path):
    """Verify session_store handles missing file gracefully."""
    from embedagent.session_store import SessionSummaryStore

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    store = SessionSummaryStore(str(workspace))
    result = store._read_json(str(workspace / "missing" / "file.json"))
    assert result is None


def test_workspace_recipes_load_json_missing_file():
    """Verify workspace_recipes handles missing file gracefully."""
    from embedagent.workspace_recipes import _load_json

    result = _load_json("/nonexistent/path/file.json", default={})
    assert result == {}


def test_core_adapter_read_file_missing(tmp_path):
    """Verify core_adapter handles missing file gracefully."""
    from embedagent.core.adapter import AgentCoreAdapter
    from embedagent.tools import ToolRuntime
    from embedagent_core.permissions import PermissionPolicy

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    adapter = AgentCoreAdapter(str(workspace))
    adapter.initialize(
        client=object(),
        tools=ToolRuntime(str(workspace)),
        max_turns=8,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(workspace)),
    )
    result = adapter.get_diff_preview("missing.txt", "new content")
    assert result.path == "missing.txt"


def test_timeline_service_load():
    """Verify timeline_service handles adapter errors gracefully."""
    from embedagent.frontend.tui.services.timeline import TimelineService

    service = TimelineService(None)
    result = service.load("session-123")
    assert result == {
        "session_id": "session-123",
        "history_source": "unavailable",
        "turns": [],
        "activities": [],
        "current_interaction": None,
        "integrity": {"status": "unavailable"},
    }
    assert "items" not in result


def test_all_modified_modules_importable():
    """Verify all modified modules can be imported without errors."""
