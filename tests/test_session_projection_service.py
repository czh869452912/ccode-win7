from types import SimpleNamespace

from embedagent_core.session import AssistantReply, Session
from embedagent_host.runtime.session_projection import SessionProjectionService


class _TranscriptStore(object):
    def __init__(self, events):
        self.events = list(events)

    def load_events(self, session_id):
        assert session_id == "session-1"
        return list(self.events)


def _state(session):
    return SimpleNamespace(
        session=session,
        restore_transcript_event_count=0,
        restore_stop_reason="",
        restore_consumed_event_count=0,
        operation_diagnostics={},
        runtime_config={},
        compaction_state={},
        recovery_state={},
        turn_experience={},
    )


def test_refresh_reduces_durable_session_read_models():
    session = Session(session_id="session-1")
    state = _state(session)
    service = SessionProjectionService(
        transcript_store=_TranscriptStore(
            [
                {
                    "type": "runtime_configured",
                    "session_id": "session-1",
                    "payload": {
                        "model_profile": {"name": "offline-test"},
                        "active_tool_names": ["read_file"],
                    },
                }
            ]
        ),
        summary_loader=lambda current_state: None,
    )

    assert service.refresh(state) is True
    assert state.runtime_config["model_profile"]["name"] == "offline-test"
    assert state.runtime_config["active_tool_names"] == ["read_file"]
    assert isinstance(state.operation_diagnostics, dict)
    assert isinstance(state.compaction_state, dict)
    assert isinstance(state.recovery_state, dict)
    assert isinstance(state.turn_experience, dict)


def test_history_projection_uses_the_session_projection_boundary():
    session = Session(session_id="session-1")
    session.add_user_message("hello", turn_id="turn-1", message_id="message-user")
    session.begin_step(reasoning="thinking", step_id="step-1")
    session.add_assistant_reply(
        AssistantReply(content="done", reasoning_content="thinking"),
        message_id="message-assistant",
        turn_id="turn-1",
        step_id="step-1",
    )
    state = _state(session)
    service = SessionProjectionService(
        transcript_store=_TranscriptStore([]),
        summary_loader=lambda current_state: None,
    )

    history = service.build_history(state)

    assert history["history_source"] == "session_state"
    assert history["turns"][0]["user_text"] == "hello"
    assert history["turns"][0]["steps"][0]["assistant_text"] == "done"
    assert history["activities"][0]["projection_source"] == "session_state"


def test_refresh_ignores_events_after_a_partial_restore_boundary():
    session = Session(session_id="session-1")
    state = _state(session)
    state.restore_transcript_event_count = 2
    state.restore_consumed_event_count = 1
    service = SessionProjectionService(
        transcript_store=_TranscriptStore(
            [
                {
                    "type": "runtime_configured",
                    "session_id": "session-1",
                    "payload": {"model_profile": {"name": "trusted"}},
                },
                {
                    "type": "runtime_configured",
                    "session_id": "session-1",
                    "payload": {"model_profile": {"name": "untrusted-tail"}},
                },
            ]
        ),
        summary_loader=lambda current_state: None,
    )

    service.refresh(state)

    assert state.runtime_config["model_profile"]["name"] == "trusted"


def test_restore_result_contains_all_durable_read_models():
    from embedagent_core.session_restore import SessionRestorer

    result = SessionRestorer().restore(
        [
            {
                "session_id": "session-1",
                "type": "session_meta",
                "ts": "2026-01-01T00:00:00Z",
                "payload": {"current_mode": "build"},
            },
            {
                "session_id": "session-1",
                "type": "runtime_configured",
                "payload": {
                    "model_profile": {"name": "offline-test"},
                    "active_tool_names": ["read_file"],
                },
            },
        ]
    )

    assert result.runtime_config.to_dict()["model_profile"]["name"] == "offline-test"
    assert isinstance(result.turn_experience.to_dict(), dict)
    assert result.operation_state is not None
