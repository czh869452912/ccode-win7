"""Minimal offline Agent Core session with interaction suspension and resume."""

from __future__ import unicode_literals

import json

from embedagent_core import (
    Action,
    Agent,
    AgentPorts,
    AssistantReply,
    InMemorySessionLog,
    InteractionReply,
    ModelClient,
    NoopContextAssembler,
    Observation,
    PermissionPolicy,
    PreparedToolObservation,
    ToolRuntimePort,
    UserTurn,
)


class ScriptedModel(ModelClient):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        del messages, tools
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="ask_user",
                        arguments={"question": "Continue?"},
                        call_id="example-call-1",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="done", actions=[], finish_reason="stop")

    def stream(
        self,
        messages,
        tools=None,
        on_text_delta=None,
        on_reasoning_delta=None,
    ):
        del on_reasoning_delta
        reply = self.generate(messages, tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply


class NoWorkspacePathResolver(object):
    def resolve_path(self, path, allow_missing=False):
        del path, allow_missing
        raise RuntimeError("standalone example does not expose workspace paths")


class StandaloneToolRuntime(ToolRuntimePort):
    workspace = ""
    tool_result_store = None
    projection_db = None
    _path_resolver = NoWorkspacePathResolver()

    def schemas_for(self, mode, workflow_state=None, tool_names=None):
        del mode, workflow_state, tool_names
        return []

    def tool_catalog_entry(self, tool_name):
        if tool_name != "ask_user":
            return None
        return {
            "permission_category": "read",
            "read_only": True,
            "concurrency_safe": True,
            "user_label": "Ask User",
            "progress_renderer_key": "interaction",
            "result_renderer_key": "interaction",
            "source_type": "standalone_example",
            "source_id": "examples.standalone_agent",
        }

    def execute_with_interrupt(self, name, arguments, stop_event):
        del arguments, stop_event
        return Observation(
            name,
            False,
            "the standalone example exposes no executable tools",
            {
                "error_kind": "tool_unavailable",
                "retryable": False,
                "outcome_class": "diagnostic_failure",
            },
        )

    def materialize_observation(self, session_id, action, observation):
        del session_id, action
        return PreparedToolObservation(observation=observation)

    def finalize_observation(self, commit_token):
        del commit_token

    def path_resolver(self):
        return self._path_resolver


def run_example():
    ports = AgentPorts(
        model=ScriptedModel(),
        tools=StandaloneToolRuntime(),
        session_log=InMemorySessionLog(),
        context=NoopContextAssembler(),
        permissions=PermissionPolicy(),
    )
    session = Agent.create(ports).open("standalone-example")

    waiting = session.submit(UserTurn("Ask before continuing", stream=False))
    pending = waiting.pending_interaction
    if pending is None:
        raise RuntimeError("example did not suspend for user input")

    resumed = session.submit(
        InteractionReply(
            pending.interaction_id,
            {"answer": "yes"},
            stream=False,
        )
    )
    return {
        "final_text": resumed.final_text,
        "interaction_kind": pending.kind,
        "session_id": resumed.session.session_id,
        "termination_reason": resumed.termination_reason,
        "waiting_reason": waiting.termination_reason,
    }


def main():
    print(json.dumps(run_example(), sort_keys=True))


if __name__ == "__main__":
    main()
