from embedagent.context_usage import ContextUsageEstimator
from embedagent.session import AssistantReply, Session


def _session_with_usage():
    session = Session(session_id="sess-usage")
    session.add_user_message("hello")
    session.add_assistant_reply(
        AssistantReply(
            content="world",
            actions=[],
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        )
    )
    return session


def test_context_usage_prefers_valid_assistant_usage_and_estimates_trailing_messages():
    session = _session_with_usage()
    session.add_user_message("tail " * 20)

    estimate = ContextUsageEstimator(chars_per_token=4.0).estimate_session(
        session,
        context_window=1000,
        reserve_tokens=100,
    )

    assert estimate.tokens > 120
    assert estimate.usage_tokens == 120
    assert estimate.trailing_estimate_tokens > 0
    assert estimate.source == "provider_usage_plus_estimate"
    assert estimate.threshold_tokens == 900
    assert estimate.percent is not None


def test_context_usage_ignores_stale_usage_before_latest_compaction():
    session = _session_with_usage()
    session.add_compact_boundary("summary", 1, "build", {})

    estimate = ContextUsageEstimator(chars_per_token=4.0).estimate_session(
        session,
        context_window=1000,
        reserve_tokens=100,
    )

    assert estimate.tokens is None
    assert estimate.source == "unknown_after_compaction"
    assert estimate.percent is None


def test_context_usage_estimates_when_no_provider_usage_exists():
    session = Session(session_id="sess-estimate")
    session.add_user_message("hello " * 50)

    estimate = ContextUsageEstimator(chars_per_token=4.0).estimate_session(
        session,
        context_window=1000,
        reserve_tokens=100,
    )

    assert estimate.tokens > 0
    assert estimate.usage_tokens == 0
    assert estimate.source == "estimate"
