"""Guard the transcript-backed session-history boundary."""

import json
from pathlib import Path

from embedagent.frontend.gui.backend.protocol_payloads import serialize_session_bootstrap

ROOT = Path(__file__).resolve().parents[1]
HOST_SOURCE = ROOT / "packages" / "embedagent-host" / "src" / "embedagent_host"
CORE_SOURCE = ROOT / "packages" / "embedagent-core" / "src" / "embedagent_core"
GUI_SOURCE = ROOT / "src" / "embedagent" / "frontend" / "gui" / "backend"
TUI_TIMELINE_SOURCE = ROOT / "src" / "embedagent" / "frontend" / "tui" / "services" / "timeline.py"


def _read(path):
    return path.read_text(encoding="utf-8")


def test_no_durable_timeline_store_or_timeline_api_is_active():
    active_paths = list(CORE_SOURCE.rglob("*.py")) + list(HOST_SOURCE.rglob("*.py"))
    active_paths += list(GUI_SOURCE.rglob("*.py"))
    assert not any(path.name == "timeline_store.py" for path in active_paths)
    source = "\n".join(_read(path) for path in active_paths)
    assert "timeline.jsonl" not in source
    assert "get_timeline" not in source
    assert "load_timeline" not in source
    assert "timeline_replay" not in source


def test_history_projection_is_transcript_backed_and_bootstrap_owned():
    adapter_source = _read(HOST_SOURCE / "inprocess_adapter.py")
    bootstrap_source = _read(HOST_SOURCE / "runtime" / "session_bootstrap_service.py")
    history_source = _read(HOST_SOURCE / "runtime" / "session_history.py")
    projection_source = _read(HOST_SOURCE / "runtime" / "session_projection.py")

    assert "TranscriptStore" in adapter_source
    assert "SessionProjectionService" in adapter_source
    assert "SessionHistoryAssembler" not in adapter_source
    assert "history_loader" in bootstrap_source
    assert "transcript_event_count" in history_source
    assert "OperationLogReducer" in projection_source
    assert "TurnExperienceReducer" in projection_source
    assert "timeline_store" not in adapter_source
    assert "timeline_store" not in bootstrap_source
    assert "timeline_store" not in history_source


def test_tui_timeline_view_reads_bootstrap_history_only():
    source = _read(TUI_TIMELINE_SOURCE)
    assert "get_session_bootstrap" in source
    assert 'payload.get("history")' in source
    assert "get_timeline" not in source
    assert "load_timeline" not in source


def test_gui_session_bootstrap_serializes_history_without_replay_payload():
    payload = serialize_session_bootstrap(
        {
            "snapshot": {"session_id": "session-1", "status": "idle"},
            "history": {"activities": [{"kind": "user", "content": "hello"}]},
        }
    )
    encoded = json.dumps(payload, sort_keys=True)
    assert payload["history"]["activities"][0]["kind"] == "user"
    assert "timeline" not in payload
    assert "replay" not in payload
    assert "timeline" not in encoded
    assert "replay" not in encoded


def test_hosted_command_permissions_use_the_core_action_pipeline_once():
    adapter_source = _read(HOST_SOURCE / "inprocess_adapter.py")
    command_source = _read(HOST_SOURCE / "hosted_command_service.py")
    query_source = _read(CORE_SOURCE / "query_engine.py")
    action_source = _read(CORE_SOURCE / "agent_tool_action_service.py")
    api_source = _read(CORE_SOURCE / "api.py")
    runner_source = _read(CORE_SOURCE / "runner.py")

    assert "_host_submit_command_turn" in command_source
    assert "_record_pending_permission" not in command_source
    assert "_record_command_pending_permission" not in adapter_source
    assert "permission_pending_handler=self._build_permission_pending_result" in query_source
    assert "self._permission_pending_handler(" in action_source
    assert "_host_record_pending_permission" not in api_source
    assert "host_record_pending_permission" not in runner_source
