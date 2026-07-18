from embedagent_host.runtime.agent_applications import (
    agent_application_capability_payload,
    base_agent_application_registry,
)

from embedagent.product_catalog import product_agent_application_registry


def test_base_agent_matrix_excludes_workflow_specialization():
    registry = base_agent_application_registry()
    ids = [record.application_id for record in registry.application_records]
    assert ids == ["embedagent.generic", "embedagent.python", "embedagent.html"]
    for application_id in ids:
        payload = agent_application_capability_payload(application_id, registry=registry)
        assert payload["agentApplication"]["applicationId"] == application_id
        assert payload["agentApplication"]["workflowPackageIds"] == []


def test_product_agent_matrix_declares_c_cpp_alongside_base_agents():
    registry = product_agent_application_registry()
    payload = agent_application_capability_payload("embedagent.default_c_cpp", registry=registry)
    ids = [item["applicationId"] for item in payload["agentApplications"]]
    assert ids[0] == "embedagent.default_c_cpp"
    assert ids[1:] == ["embedagent.generic", "embedagent.python", "embedagent.html"]
    assert payload["agentApplication"]["workflowPackageIds"]
    assert payload["agentApplication"]["active"] is True


def test_injected_specialized_registry_projects_without_renderer_knowledge():
    from embedagent_host.runtime.agent_applications import (
        AgentApplicationRecord,
        AgentApplicationRegistry,
    )
    from embedagent_host.runtime.profiles import generic_agent_profile

    custom = AgentApplicationRecord(
        application_id="tests.specialized",
        label="Specialized Agent",
        profile_id="tests.specialized.profile",
        profile_factory=generic_agent_profile,
        source_type="project",
        source_id="workspace-extension",
        workflow_package_ids=("tests.workflow",),
        metadata={"domain": "specialized"},
    )
    registry = AgentApplicationRegistry(
        application_records=(custom,),
        default_application_id="tests.specialized",
    )
    payload = agent_application_capability_payload("tests.specialized", registry=registry)
    assert payload["agentApplication"]["applicationId"] == "tests.specialized"
    assert payload["agentApplication"]["workflowPackageIds"] == ["tests.workflow"]
    assert payload["agentApplication"]["sourceType"] == "project"
