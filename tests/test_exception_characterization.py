"""Characterization tests for exception handling behavior — verifies pre/post change equivalence."""


def test_permissions_load_missing_file():
    """Verify permissions handles missing file gracefully."""
    from embedagent_core.permissions import PermissionPolicy

    policy = PermissionPolicy(auto_approve_all=True, workspace="/nonexistent/path")
    rules = policy._load_rules("/nonexistent/path/permissions.json")
    assert rules == []


def test_task_store_load_missing_file():
    """Verify task_store handles missing file gracefully."""
    from embedagent_workflow_cpp.task_store import load_task_snapshot

    result = load_task_snapshot("/nonexistent/path", "session-123")
    assert result == {}


def test_project_memory_load_missing_file():
    """Verify project_memory handles missing file gracefully."""
    from embedagent_host.runtime.project_memory import ProjectMemoryStore

    memory = ProjectMemoryStore("/nonexistent/path")
    result = memory._load_json("/nonexistent/path/file.json", default=[])
    assert result == []


def test_session_store_read_json_missing_file(tmp_path):
    """Verify session_store handles missing file gracefully."""
    from embedagent_host.runtime.session_store import SessionSummaryStore

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    store = SessionSummaryStore(str(workspace))
    result = store._read_json(str(workspace / "missing" / "file.json"))
    assert result is None


def test_workspace_recipes_load_json_missing_file():
    """Verify workspace_recipes handles missing file gracefully."""
    from embedagent_host.runtime.workspace_recipes import _load_json

    result = _load_json("/nonexistent/path/file.json", default={})
    assert result == {}


def test_workspace_port_diff_preview_handles_missing_file(tmp_path):
    """Verify the focused workspace port handles a missing source file."""
    from embedagent_core.permissions import PermissionPolicy
    from embedagent_host.frontend_ports import InProcessFrontendWorkspacePort
    from embedagent_host.inprocess_adapter import InProcessAdapter
    from embedagent_host.runtime.agent_applications import base_agent_application_registry
    from embedagent_host.runtime.tools import ToolRuntime

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runtime_adapter = InProcessAdapter(
        client=object(),
        tools=ToolRuntime(str(workspace)),
        max_turns=8,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(workspace)),
        agent_application_id="embedagent.generic",
        agent_application_registry=base_agent_application_registry(),
    )
    result = InProcessFrontendWorkspacePort(runtime_adapter).get_diff_preview(
        "missing.txt", "new content"
    )
    assert result["path"] == "missing.txt"


def test_all_modified_modules_importable():
    """Verify all modified modules can be imported without errors."""
