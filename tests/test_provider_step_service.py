import concurrent.futures
import threading

from embedagent_core.agent_effects import (
    AssembleContextEffect,
    ContextAssembled,
    EffectFailed,
    ProviderCompleted,
    RequestProviderEffect,
)
from embedagent_core.model import ModelClientError
from embedagent_core.provider_step_service import ProviderObserver, ProviderStepService
from embedagent_core.session import AssistantReply, ContextAssemblyResult, Session
from embedagent_core.session_log import InMemorySessionLog
from embedagent_core.turn_snapshot_service import TurnSnapshotService


class StaticContextAssembler(object):
    reducers = {}

    def build_messages(
        self,
        session,
        mode_name,
        tools=None,
        workflow_state="",
        force_compact=False,
    ):
        del session, mode_name, tools, workflow_state
        return ContextAssemblyResult(
            messages=[{"role": "user", "content": "hello"}],
            used_chars=5,
            approx_tokens=2,
            compacted=bool(force_compact),
            summarized_turns=0,
            recent_turns=1,
            policy=None,
            budget=None,
            stats=None,
        )


class StaticExtensionHost(object):
    def __init__(self):
        self.schemas = [
            {
                "type": "function",
                "function": {"name": "read_file", "parameters": {"type": "object"}},
            }
        ]

    def schemas_for_active_tools(self, mode_name, workflow_state):
        del mode_name, workflow_state
        return list(self.schemas)

    def apply_context_patch(
        self,
        session,
        mode_name,
        workflow_state,
        assembly,
        force_compact=False,
    ):
        del session, mode_name, workflow_state, force_compact
        return assembly


class StaticTools(object):
    def catalog_entries(self):
        return [
            {
                "name": "read_file",
                "source_type": "builtin",
                "source_id": "core",
            }
        ]

    def local_resources(self):
        return {}

    def runtime_environment_snapshot(self):
        return {"python": "3.8"}


class DoneClient(object):
    def __init__(self):
        self.calls = []

    def generate(self, messages, tools=None):
        self.calls.append((messages, tools))
        return AssistantReply("done", finish_reason="stop")

    def stream(
        self,
        messages,
        tools=None,
        on_text_delta=None,
        on_reasoning_delta=None,
    ):
        self.calls.append((messages, tools))
        if on_reasoning_delta is not None:
            on_reasoning_delta("thinking")
        if on_text_delta is not None:
            on_text_delta("done")
        return AssistantReply("done", finish_reason="stop")


class ContextLimitClient(DoneClient):
    def generate(self, messages, tools=None):
        del messages, tools
        raise ModelClientError("maximum context length exceeded")


def _service(client, session_log=None):
    return ProviderStepService(
        context_assembler=StaticContextAssembler(),
        extension_host=StaticExtensionHost(),
        snapshot_service=TurnSnapshotService(),
        tools=StaticTools(),
        client=client,
        session_log=session_log or InMemorySessionLog(),
        retry_max_attempts=1,
    )


def test_assemble_context_builds_detached_snapshot_without_committing():
    session_log = InMemorySessionLog()
    session = Session(session_id="session-1")
    service = _service(DoneClient(), session_log=session_log)
    effect = AssembleContextEffect(
        "context-1",
        "turn-1",
        "step-1",
        "build",
        "chat",
    )

    result = service.assemble_context(effect, session)

    assert isinstance(result, ContextAssembled)
    assert result.snapshot.messages == result.assembly.messages
    assert result.snapshot.tool_schemas == StaticExtensionHost().schemas
    assert result.snapshot.active_tool_names == ["read_file"]
    assert session_log.load_events(session.session_id) == []
    assert [event.event_type for event in result.events] == [
        "operation_finished",
        "operation_started",
        "context_snapshot",
        "operation_finished",
    ]


def test_request_provider_uses_snapshot_and_forwards_stream_deltas():
    client = DoneClient()
    service = _service(client)
    context = service.assemble_context(
        AssembleContextEffect(
            "context-1",
            "turn-1",
            "step-1",
            "build",
            "",
        ),
        Session(session_id="session-1"),
    )
    text_deltas = []
    reasoning_deltas = []

    result = service.request_provider(
        RequestProviderEffect("provider-1", context.snapshot, True),
        ProviderObserver(text_deltas.append, reasoning_deltas.append),
    )

    assert isinstance(result, ProviderCompleted)
    assert result.reply.content == "done"
    assert client.calls == [(context.snapshot.messages, context.snapshot.tool_schemas)]
    assert text_deltas == ["done"]
    assert reasoning_deltas == ["thinking"]
    assert result.events[-1].event_type == "operation_finished"


def test_context_limit_is_typed_failure_without_service_retry():
    service = _service(ContextLimitClient())
    context = service.assemble_context(
        AssembleContextEffect(
            "context-1",
            "turn-1",
            "step-1",
            "build",
            "",
        ),
        Session(session_id="session-1"),
    )

    result = service.request_provider(
        RequestProviderEffect("provider-1", context.snapshot, False),
        ProviderObserver(),
    )

    assert isinstance(result, EffectFailed)
    assert result.error_kind == "context_limit"
    assert result.effect_id == "provider-1"
    assert result.events[-1].event_type == "operation_interrupted"


def test_last_snapshot_is_isolated_between_concurrent_session_threads():
    service = _service(DoneClient())
    assembled = threading.Barrier(2)

    def build_snapshot(index):
        result = service.assemble_context(
            AssembleContextEffect(
                "context-%d" % index,
                "turn-%d" % index,
                "step-%d" % index,
                "build",
                "",
            ),
            Session(session_id="session-%d" % index),
        )
        assembled.wait()
        return result.snapshot.snapshot_id, service.last_snapshot().snapshot_id

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        snapshots = list(executor.map(build_snapshot, (1, 2)))

    assert snapshots[0][0] == snapshots[0][1]
    assert snapshots[1][0] == snapshots[1][1]
