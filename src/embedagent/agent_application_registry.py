from __future__ import annotations

from embedagent_host.runtime.agent_applications import (
    BUILTIN_AGENT_APPLICATION_RECORDS,
    AgentApplicationRegistry,
)

from embedagent.workflow_packages.c_cpp.application_record import (
    DEFAULT_C_CPP_AGENT_APPLICATION_ID,
    default_c_cpp_agent_application_record,
)


def product_agent_application_registry() -> AgentApplicationRegistry:
    return AgentApplicationRegistry(
        application_records=(default_c_cpp_agent_application_record(),)
        + tuple(BUILTIN_AGENT_APPLICATION_RECORDS),
        default_application_id=DEFAULT_C_CPP_AGENT_APPLICATION_ID,
    )
