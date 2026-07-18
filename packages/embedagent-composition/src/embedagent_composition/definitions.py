from __future__ import annotations

from .model import AgentProductDefinition, ComponentRef


def profile_agent_definition(agent_id: str, profile_component_id: str) -> AgentProductDefinition:
    return AgentProductDefinition(
        agent_id=agent_id,
        profile=ComponentRef(profile_component_id),
        providers=(ComponentRef("embedagent-protocol"),),
        tools=(ComponentRef("embedagent-composition"),),
        host=ComponentRef("embedagent-host"),
    )


def generic_agent_definition() -> AgentProductDefinition:
    return profile_agent_definition("embedagent.generic", "embedagent-generic")


def python_agent_definition() -> AgentProductDefinition:
    return profile_agent_definition("embedagent.python", "embedagent-python")


def html_agent_definition() -> AgentProductDefinition:
    return profile_agent_definition("embedagent.html", "embedagent-html")


def c_cpp_agent_definition() -> AgentProductDefinition:
    return AgentProductDefinition(
        agent_id="embedagent.default_c_cpp",
        profile=ComponentRef("embedagent-cpp-profile"),
        providers=(ComponentRef("embedagent-protocol"),),
        workflows=(ComponentRef("embedagent-workflow-cpp"),),
        tools=(ComponentRef("embedagent-composition"),),
        host=ComponentRef("embedagent-host"),
    )
