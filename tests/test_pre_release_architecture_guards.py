from __future__ import unicode_literals

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ACTIVE_SOURCE_FILES = [
    ROOT / "src/embedagent/protocol/__init__.py",
    ROOT / "src/embedagent/session_projector.py",
    ROOT / "src/embedagent/core/adapter.py",
    ROOT / "src/embedagent/inprocess_adapter.py",
    ROOT / "src/embedagent/frontend/gui/backend/server.py",
    ROOT / "src/embedagent/frontend/gui/webapp/src/state-helpers.js",
    ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx",
    ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js",
    ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js",
]


def _read(path):
    return path.read_text(encoding="utf-8")


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
