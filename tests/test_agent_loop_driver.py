import inspect
import threading
from dataclasses import dataclass

import pytest
from embedagent_core.agent_effects import (
    AssembleContextEffect,
    ContextAssembled,
    EffectFailed,
    ExecutePreparedToolBatchEffect,
    FrozenToolAction,
    PreparedToolInvocation,
    PrepareToolBatchEffect,
    ProviderCompleted,
    RequestProviderEffect,
    ToolBatchCompleted,
    ToolBatchPrepared,
)
from embedagent_core.agent_kernel import KernelCursor, KernelStep
from embedagent_core.agent_loop import AgentLoop
from embedagent_core.agent_loop_continuation import DefaultAgentLoopContinuationPolicy
from embedagent_core.ports import StrictSessionRestorePolicy
from embedagent_core.session import (
    Action,
    AssistantReply,
    ContextAssemblyResult,
    LoopTransition,
    Observation,
    Session,
)
from embedagent_core.session_journal import EventIntent, SessionJournal
from embedagent_core.session_log import InMemorySessionLog
from embedagent_core.session_reducer import SessionReducer, SessionReducerContext
from embedagent_core.turn_snapshot import TurnSnapshot


def _assembly():
    return ContextAssemblyResult(
        messages=[{"role": "user", "content": "hello"}],
        used_chars=5,
        approx_tokens=2,
        compacted=False,
        summarized_turns=0,
        recent_turns=1,
        policy=None,
        budget=None,
        stats=None,
    )


def _snapshot():
    return TurnSnapshot(
        snapshot_id="snapshot-1",
        session_id="session-1",
        turn_id="turn-1",
        step_id="step-1",
        mode_name="build",
        workflow_state="",
        messages=[{"role": "user", "content": "hello"}],
        tool_schemas=[],
    )


def _prepared_invocation():
    action = Action("read_file", {"path": "README.md"}, "call-1")
    frozen = FrozenToolAction.from_action(action)
    return PreparedToolInvocation(
        invocation_id="tool:m-assistant-turn-1-step-1-1:0",
        provider_call_id=action.call_id,
        source_index=0,
        original_action=frozen,
        effective_action=frozen,
        permission_category="read",
        read_only=True,
        concurrency_safe=True,
        presentation_json="{}",
        source_type="builtin",
        source_id="read_file",
        replay_safe=False,
    )


class RecordingJournal(object):
    def __init__(self, calls):
        self.calls = calls

    def commit(self, session, context, intents):
        del session, context
        events = []
        for intent in intents:
            self.calls.append("commit:%s" % intent.payload["label"])
            events.append(
                {
                    "type": intent.event_type,
                    "payload": dict(intent.payload),
                }
            )
        return type("Commit", (), {"events": tuple(events)})()


class SequenceKernel(object):
    def __init__(self):
        self.accepted = []

    def start(self, turn_id, mode_name, workflow_state, source, stream=False, step_index=1):
        del turn_id, mode_name, workflow_state, source, stream, step_index
        cursor = KernelCursor("context", "context-1", 1, 0, False)
        return KernelStep(
            cursor,
            (EventIntent("operation_started", {"label": "context_started"}),),
            AssembleContextEffect("context-1", "turn-1", "step-1", "build", ""),
        )

    def accept(self, cursor, result):
        if result.effect_id != cursor.expected_effect_id:
            raise ValueError("effect_result_mismatch")
        self.accepted.append(result)
        if cursor.phase == "context":
            next_cursor = KernelCursor("provider", "provider-1", 1, 1, False)
            return KernelStep(
                next_cursor,
                (EventIntent("operation_started", {"label": "provider_started"}),),
                RequestProviderEffect("provider-1", _snapshot(), False),
            )
        if cursor.phase == "provider":
            action = Action("read_file", {"path": "README.md"}, "call-1")
            next_cursor = KernelCursor("tool_prepare", "prepare-1", 1, 1, False)
            return KernelStep(
                next_cursor,
                (EventIntent("tool_call", {"label": "tool_planned"}),),
                PrepareToolBatchEffect(
                    "prepare-1",
                    "m-assistant-turn-1-step-1-1",
                    (FrozenToolAction.from_action(action),),
                    "build",
                    "",
                ),
            )
        if cursor.phase == "tool_prepare":
            prepared = _prepared_invocation()
            next_cursor = KernelCursor("tool_execute", "tools-1", 1, 1, False)
            return KernelStep(
                next_cursor,
                (
                    EventIntent(
                        "operation_started",
                        {"label": "tool_execution_started"},
                    ),
                ),
                ExecutePreparedToolBatchEffect("tools-1", (prepared,)),
            )
        return KernelStep(
            KernelCursor("complete", "", 1, 1, False),
            (EventIntent("operation_finished", {"label": "completed"}),),
            outcome=LoopTransition("completed", "done", turns_used=1),
            post_commit_tokens=result.commit_tokens,
        )


class RecordingProviderSteps(object):
    def __init__(self, calls, stale=False):
        self.calls = calls
        self.stale = stale

    def assemble_context(self, effect, session):
        del session
        self.calls.append("execute:context")
        effect_id = "stale-context" if self.stale else effect.effect_id
        return ContextAssembled(effect_id, _assembly(), _snapshot())

    def request_provider(self, effect, observer):
        del observer
        self.calls.append("execute:provider")
        return ProviderCompleted(
            effect.effect_id,
            AssistantReply(
                "",
                actions=[Action("read_file", {"path": "README.md"}, "call-1")],
                finish_reason="tool_calls",
            ),
        )


class RecordingToolActions(object):
    def __init__(self, calls):
        self.calls = calls
        self.finalized = []

    def prepare(self, effect, session, **kwargs):
        del session, kwargs
        self.calls.append("prepare:tool")
        return ToolBatchPrepared(
            effect.effect_id,
            invocations=(_prepared_invocation(),),
        )

    def execute_prepared(self, effect, session, **kwargs):
        del session, kwargs
        self.calls.append("execute:tool")
        return ToolBatchCompleted(
            effect.effect_id,
            observations=(Observation("read_file", True, None, {"path": "README.md"}),),
            commit_tokens=("token-1",),
        )

    def finalize(self, tokens):
        self.finalized.extend(tokens)


def _loop(calls, kernel=None, provider_steps=None, tool_actions=None, journal=None):
    return AgentLoop(
        kernel or SequenceKernel(),
        journal or RecordingJournal(calls),
        provider_steps or RecordingProviderSteps(calls),
        tool_actions or RecordingToolActions(calls),
        DefaultAgentLoopContinuationPolicy(),
    )


def test_driver_run_has_no_optional_callback_bag():
    parameters = set(inspect.signature(AgentLoop.run).parameters)

    assert parameters.isdisjoint(
        {
            "on_text_delta",
            "on_reasoning_delta",
            "on_tool_start",
            "on_tool_finish",
            "on_context_result",
            "on_step_start",
            "on_step_finish",
            "permission_handler",
            "user_input_handler",
        }
    )


def test_driver_commits_prepared_execution_start_before_dispatch():
    calls = []
    tools = RecordingToolActions(calls)

    result = _loop(calls, tool_actions=tools).run(
        Session(session_id="session-1"),
        SessionReducerContext(),
        "turn-1",
        "build",
        "",
    )

    assert calls == [
        "commit:context_started",
        "execute:context",
        "commit:provider_started",
        "execute:provider",
        "commit:tool_planned",
        "prepare:tool",
        "commit:tool_execution_started",
        "execute:tool",
        "commit:completed",
    ]
    assert result.transition.reason == "completed"
    assert tools.finalized == ["token-1"]


class FailingJournal(RecordingJournal):
    def __init__(self, calls, label):
        super(FailingJournal, self).__init__(calls)
        self.label = label

    def commit(self, session, context, intents):
        for intent in intents:
            if intent.payload.get("label") == self.label:
                self.calls.append("commit:%s" % self.label)
                raise IOError("append failed")
        return super(FailingJournal, self).commit(session, context, intents)


def test_driver_does_not_dispatch_when_execution_start_commit_fails():
    calls = []
    journal = FailingJournal(calls, "tool_execution_started")

    with pytest.raises(IOError, match="append failed"):
        _loop(calls, journal=journal).run(
            Session(session_id="session-1"),
            SessionReducerContext(),
            "turn-1",
            "build",
            "",
        )

    assert "prepare:tool" in calls
    assert "execute:tool" not in calls


class CancelKernel(SequenceKernel):
    def accept(self, cursor, result):
        assert isinstance(result, EffectFailed)
        assert result.error_kind == "cancelled"
        return KernelStep(
            KernelCursor("complete", "", 0, 0, False),
            (EventIntent("operation_interrupted", {"label": "cancelled"}),),
            outcome=LoopTransition("aborted", "cancelled"),
        )


def test_driver_turns_pre_effect_cancellation_into_typed_failure():
    calls = []
    cancel = threading.Event()
    cancel.set()

    result = _loop(calls, kernel=CancelKernel()).run(
        Session(session_id="session-1"),
        SessionReducerContext(),
        "turn-1",
        "build",
        "",
        cancel=cancel,
    )

    assert result.transition.reason == "aborted"
    assert calls == ["commit:context_started", "commit:cancelled"]


class SafetyKernel(SequenceKernel):
    def accept(self, cursor, result):
        if cursor.phase == "tool_execute":
            assert isinstance(result, EffectFailed)
            assert result.error_kind == "safety_limit"
            return KernelStep(
                KernelCursor("complete", "", 1, 1, False),
                (EventIntent("operation_interrupted", {"label": "safety_limit"}),),
                outcome=LoopTransition(
                    "max_turns",
                    result.message,
                    turns_used=int(result.metadata["turns_used"]),
                    metadata=dict(result.metadata),
                ),
            )
        return super(SafetyKernel, self).accept(cursor, result)


def test_driver_enforces_explicit_turn_safety_fuse_before_next_effect():
    calls = []

    result = _loop(calls, kernel=SafetyKernel()).run(
        Session(session_id="session-1"),
        SessionReducerContext(),
        "turn-1",
        "build",
        "",
        max_turns=1,
    )

    assert result.transition.reason == "max_turns"
    assert result.turns_used == 1
    assert calls[-1] == "commit:safety_limit"
    assert "commit:next_context" not in calls
    assert calls.count("execute:context") == 1


class DiscardingToolActions(RecordingToolActions):
    def execute_prepared(self, effect, session, **kwargs):
        del session, kwargs
        self.calls.append("execute:tool")
        return ToolBatchCompleted(
            effect.effect_id,
            observations=(
                Observation(
                    "read_file",
                    False,
                    "discarded",
                    {"error_kind": "discarded", "outcome_class": "cancelled"},
                ),
            ),
        )


def test_driver_does_not_treat_discarded_parallel_result_as_cancellation():
    calls = []

    result = _loop(calls, tool_actions=DiscardingToolActions(calls)).run(
        Session(session_id="session-1"),
        SessionReducerContext(),
        "turn-1",
        "build",
        "",
    )

    assert result.transition.reason == "completed"
    assert calls[-1] == "commit:completed"


def test_driver_rejects_stale_effect_result():
    calls = []
    loop = _loop(calls, provider_steps=RecordingProviderSteps(calls, stale=True))

    with pytest.raises(ValueError, match="^effect_result_mismatch$"):
        loop.run(
            Session(session_id="session-1"),
            SessionReducerContext(),
            "turn-1",
            "build",
            "",
        )


@dataclass(frozen=True)
class UnsupportedEffect:
    effect_id: str


class UnsupportedKernel(SequenceKernel):
    def start(self, turn_id, mode_name, workflow_state, source, stream=False, step_index=1):
        del turn_id, mode_name, workflow_state, source, stream, step_index
        return KernelStep(
            KernelCursor("unsupported", "unsupported-1", 1, 0, False),
            (),
            UnsupportedEffect("unsupported-1"),
        )


def test_driver_rejects_unknown_effect_type():
    calls = []

    with pytest.raises(TypeError, match="^unsupported agent effect$"):
        _loop(calls, kernel=UnsupportedKernel()).run(
            Session(session_id="session-1"),
            SessionReducerContext(),
            "turn-1",
            "build",
            "",
        )


class RaisingObserver(object):
    def __init__(self):
        self.calls = 0

    def on_event(self, event_type, payload):
        del event_type, payload
        self.calls += 1
        raise RuntimeError("observer failed")


class DurableKernel(object):
    def start(self, turn_id, mode_name, workflow_state, source, stream=False, step_index=1):
        del turn_id, mode_name, workflow_state, source, stream, step_index
        return KernelStep(
            KernelCursor("context", "context-1", 1, 0, False),
            (EventIntent("session_meta", {"current_mode": "build"}),),
            AssembleContextEffect("context-1", "turn-1", "step-1", "build", ""),
        )

    def accept(self, cursor, result):
        assert result.effect_id == cursor.expected_effect_id
        return KernelStep(
            KernelCursor("complete", "", 1, 0, False),
            (EventIntent("operation_finished", {"operation_id": "context-1"}),),
            outcome=LoopTransition("completed", "done"),
        )


def test_observer_failure_does_not_rollback_or_repeat_committed_event():
    calls = []
    session_log = InMemorySessionLog()
    journal = SessionJournal(session_log, SessionReducer())
    observer = RaisingObserver()
    loop = _loop(calls, kernel=DurableKernel(), journal=journal)
    session = Session(session_id="session-1")

    result = loop.run(
        session,
        SessionReducerContext(),
        "turn-1",
        "build",
        "",
        observer=observer,
    )

    assert result.transition.reason == "completed"
    assert observer.calls == 1
    events = session_log.load_events("session-1")
    assert [event["type"] for event in events] == ["session_meta", "operation_finished"]
    restored = journal.restore("session-1", StrictSessionRestorePolicy())
    assert restored.current_mode == "build"
