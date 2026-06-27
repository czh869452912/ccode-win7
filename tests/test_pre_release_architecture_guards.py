from __future__ import unicode_literals

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = (".py", ".js", ".jsx")

ACTIVE_SOURCE_FILES = [
    ROOT / "src/embedagent/protocol/__init__.py",
    ROOT / "src/embedagent/session_projector.py",
    ROOT / "src/embedagent/core/adapter.py",
    ROOT / "src/embedagent/inprocess_adapter.py",
    ROOT / "src/embedagent/frontend/gui/backend/server.py",
    ROOT / "src/embedagent/frontend/gui/webapp/src/state-helpers.js",
    ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx",
    ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js",
    ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/activity-state.js",
]


def _read(path):
    return path.read_text(encoding="utf-8")


def _relative(path):
    return path.relative_to(ROOT).as_posix()


def _source_files_under(*relative_roots, **kwargs):
    suffixes = kwargs.get("suffixes", SOURCE_SUFFIXES)
    files = []
    for relative_root in relative_roots:
        root = ROOT / relative_root
        if root.is_file():
            candidates = [root]
        else:
            candidates = list(root.rglob("*"))
        for path in candidates:
            if not path.is_file():
                continue
            rel = _relative(path)
            if "__pycache__" in path.parts:
                continue
            if "/frontend/gui/static/" in rel:
                continue
            if path.suffix in suffixes:
                files.append(path)
    return files


def test_no_timeline_replay_snapshot_contract_in_active_source():
    forbidden = (
        "timeline" + "_replay_status",
        "timeline" + "_first_seq",
        "timeline" + "_last_seq",
        "timeline" + "_integrity",
    )
    offenders = []
    for path in ACTIVE_SOURCE_FILES:
        text = _read(path)
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (path.relative_to(ROOT), token))
    assert offenders == []


def test_no_session_timeline_api_in_active_source():
    files = [
        ROOT / "src/embedagent/protocol/__init__.py",
        ROOT / "src/embedagent/core/adapter.py",
        ROOT / "src/embedagent/inprocess_adapter.py",
        ROOT / "src/embedagent/frontend/tui/services/timeline.py",
    ]
    offenders = []
    for path in files:
        text = _read(path)
        if "get_session" + "_timeline" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_no_core_flat_timeline_builder_name():
    text = _read(ROOT / "src/embedagent/session_history.py")
    assert "build_flat" + "_timeline" not in text


def test_no_tui_flat_or_event_history_projection_contract():
    files = [
        ROOT / "src/embedagent/session_history.py",
        ROOT / "src/embedagent/frontend/tui/controller.py",
        ROOT / "src/embedagent/frontend/tui/frontend_adapter.py",
        ROOT / "src/embedagent/frontend/tui/services/timeline.py",
        ROOT / "src/embedagent/frontend/tui/views/timeline.py",
        ROOT / "src/embedagent/frontend/tui/views/__init__.py",
    ]
    forbidden = [
        "build_flat" + "_history",
        "Flat" + "TimelineView",
        "flat" + "_timeline",
        "get" + "_timeline_data",
        "update" + "_flat_timeline",
        "handle" + "_item_updated",
        "handle" + "_item_completed",
        "format" + "_timeline_records",
        'payload.get("events")',
        '"items": []',
    ]
    offenders = []
    for path in files:
        text = _read(path)
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (path.relative_to(ROOT), token))
    assert offenders == []


def test_no_session_view_clear_uses_timeline_payload():
    files = [
        ROOT / "src/embedagent/inprocess_adapter.py",
        ROOT / "src/embedagent/frontend/gui/webapp/src/store.js",
    ]
    offenders = []
    for path in files:
        text = _read(path)
        if "clear" + "_timeline" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_gui_session_runtime_projector_is_removed():
    assert not (
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js"
    ).exists()


def test_gui_backend_routes_do_not_use_active_core_proxy():
    text = _read(ROOT / "src/embedagent/frontend/gui/backend/server.py")
    assert "_ActiveCoreProxy" not in text
    assert "self.core" not in text


def test_no_timeline_reload_route_or_metadata_in_active_gui_backend():
    files = [
        ROOT / "src/embedagent/frontend/gui/backend/server.py",
        ROOT / "src/embedagent/frontend/gui/backend/session_events.py",
        ROOT / "src/embedagent/inprocess_adapter.py",
        ROOT / "src/embedagent/core/adapter.py",
    ]
    offenders = []
    for path in files:
        text = _read(path)
        for token in (
            "/api/sessions/{session_id}/events",
            "_timeline_event",
            "load_session" + "_events_after",
        ):
            if token in text:
                offenders.append("%s contains %s" % (path.relative_to(ROOT), token))
    assert offenders == []


def test_no_legacy_task_tool_execution_contract_in_tests():
    legacy_tool = "manage" + "_todos"
    offenders = []
    for path in (ROOT / "tests").glob("test_*.py"):
        text = _read(path)
        forbidden = (
            'execute("%s"' % legacy_tool,
            "execute('%s'" % legacy_tool,
            '"tool_name", "%s"' % legacy_tool,
            "'tool_name', '%s'" % legacy_tool,
        )
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (path.relative_to(ROOT), token))
    assert offenders == []


def test_gui_backend_server_keeps_route_registration_delegated():
    text = _read(ROOT / "src/embedagent/frontend/gui/backend/server.py")
    route_decorator_count = (
        text.count("@app.get(") + text.count("@app.post(") + text.count("@app.delete(")
    )
    assert route_decorator_count <= 2
    for helper in (
        "register_app_routes(",
        "register_session_routes(",
        "register_terminal_routes(",
        "register_source_control_routes(",
        "register_preview_routes(",
    ):
        assert helper in text


def test_query_engine_does_not_own_extension_dispatch_boundary():
    text = _read(ROOT / "src/embedagent/query_engine.py")
    assert "AgentExtensionHost(" in text
    forbidden_dispatches = (
        "self.extension_manager.allowed_tool_names(",
        "self.extension_manager.handle_tool_call(",
        "self.extension_manager.apply_tool_call_hooks(",
        "self.extension_manager.apply_tool_result_hooks(",
        "self.extension_manager.run_context_hooks(",
        "self.extension_manager.register_dynamic_tools(",
    )
    offenders = []
    for token in forbidden_dispatches:
        if token in text:
            offenders.append("query_engine.py directly dispatches %s" % token)
    assert offenders == []


def test_harness_workflow_extension_stays_behind_default_package_boundary():
    allowed_files = {
        "src/embedagent/default_extensions.py",
    }
    allowed_prefixes = ("src/embedagent/harness/",)
    offenders = []
    for path in _source_files_under("src/embedagent", suffixes=(".py",)):
        rel = _relative(path)
        if rel in allowed_files or rel.startswith(allowed_prefixes):
            continue
        text = _read(path)
        for token in (
            "CHarnessWorkflowExtension",
            "embedagent.harness.extension",
        ):
            if token in text:
                offenders.append("%s imports or constructs %s" % (rel, token))
    assert offenders == []


def test_active_source_does_not_reintroduce_tooling_pack_aliases():
    forbidden = (
        "embedagent.tooling.packs",
        "from embedagent.tooling import BUILD_LITE_PACK",
        "from embedagent.tooling import CORE_PACK",
        "from embedagent.tooling import DEBUG_LITE_PACK",
        "from embedagent.tooling import VERIFY_PACK",
        "from embedagent.tooling import PACKS",
        "from embedagent.tooling import pack_tool_names",
    )
    offenders = []
    for path in _source_files_under("src/embedagent", suffixes=(".py",)):
        rel = _relative(path)
        text = _read(path)
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (rel, token))
    assert offenders == []


def test_runtime_tool_execute_calls_stay_behind_action_or_hosted_services():
    allowed_files = {
        "src/embedagent/agent_tool_action_service.py",
        "src/embedagent/hosted_command_service.py",
        "src/embedagent/review_command.py",
    }
    allowed_prefixes = ("src/embedagent/tools/",)
    pattern = re.compile(r"\b(?:self\.)?tools\.execute\(")
    offenders = []
    for path in _source_files_under("src/embedagent", suffixes=(".py",)):
        rel = _relative(path)
        if rel in allowed_files or rel.startswith(allowed_prefixes):
            continue
        for line_number, line in enumerate(_read(path).splitlines(), start=1):
            if pattern.search(line):
                offenders.append("%s:%s calls ToolRuntime.execute" % (rel, line_number))
    assert offenders == []


def test_tool_refresh_paths_use_read_model_invalidations_not_tool_name_lists():
    tool_names = (
        "task_status",
        "report_quality_v2",
        "record_failing_evidence",
        "run_recipe",
        "list_recipes",
    )
    refresh_words = ("refresh", "invalidate", "invalidations", "tool_finished", "tool_result")
    allowed_prefixes = (
        "src/embedagent/harness/",
        "src/embedagent/tools/",
    )
    offenders = []
    for path in _source_files_under("src/embedagent"):
        rel = _relative(path)
        if rel.startswith(allowed_prefixes):
            continue
        for line_number, line in enumerate(_read(path).splitlines(), start=1):
            lowered = line.lower()
            if not any(name in line for name in tool_names):
                continue
            if not any(word in lowered for word in refresh_words):
                continue
            if "read_model_invalidations" in line or "readModelInvalidations" in line:
                continue
            offenders.append("%s:%s hard-codes workflow tool refresh" % (rel, line_number))
    assert offenders == []


def test_gui_raw_interaction_requests_do_not_synthesize_activity_records():
    files = [
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js",
        ROOT / "src/embedagent/frontend/gui/webapp/src/store.js",
    ]
    activity_tokens = (
        "interaction.created",
        "append_timeline_item",
        "turn_started",
        "tool_started",
        "assistant_delta",
    )
    offenders = []
    for path in files:
        rel = _relative(path)
        lines = _read(path).splitlines()
        for index, line in enumerate(lines):
            if "permission_request" not in line and "user_input_request" not in line:
                continue
            window = "\n".join(lines[index : index + 12])
            if any(token in window for token in activity_tokens):
                offenders.append(
                    "%s:%s synthesizes activity from raw interaction request" % (rel, index + 1)
                )
    assert offenders == []


def test_gui_runtime_state_does_not_reintroduce_removed_root_session_state():
    store_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/store.js")
    forbidden_root_state = (
        r"\n\s+sessions\s*:",
        r"\n\s+currentSessionId\s*:",
        r"\n\s+connectionState\s*:",
        r"\n\s+historyIntegrity\s*:",
    )
    offenders = []
    for pattern in forbidden_root_state:
        if re.search(pattern, store_text):
            offenders.append("store.js reintroduced root state %s" % pattern)
    forbidden_tokens = (
        "timelineFromTurns",
        "timelineFromEvents",
        "FlatTimelineView",
        "set_connection",
    )
    for path in _source_files_under(
        "src/embedagent/frontend/gui/webapp/src", suffixes=(".js", ".jsx")
    ):
        rel = _relative(path)
        text = _read(path)
        for token in forbidden_tokens:
            if token in text:
                offenders.append("%s contains %s" % (rel, token))
    assert not (
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js"
    ).exists()
    assert offenders == []
