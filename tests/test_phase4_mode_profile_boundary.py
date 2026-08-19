from __future__ import annotations

import tempfile

import pytest
from embedagent_core import (
    ApplicationConfigurationError,
    ApplicationRuntimeContribution,
    ApplicationRuntimePolicy,
    RuntimeDefinition,
)
from embedagent_core.extensions import ExtensionManager
from embedagent_core.policies import PassThroughModeRuntimePolicy
from embedagent_core.session_view import SessionReadView
from embedagent_host.frontend_errors import failure_for_exception
from embedagent_host.inprocess_adapter import InProcessAdapter
from embedagent_host.runtime.agent_applications import (
    AgentApplicationRecord,
    AgentApplicationRegistry,
    application_registry_from_runtime_contributions,
    available_agent_application_manifests,
    base_agent_application_registry,
    build_agent_application,
    generic_agent_application_manifest,
    html_agent_application_manifest,
    python_agent_application_manifest,
)
from embedagent_host.runtime.context import ContextManager
from embedagent_host.runtime.tools import ToolRuntime
from embedagent_host.runtime.workspace_intelligence import WorkspaceIntelligenceBroker


def test_context_manager_has_no_implicit_workspace_intelligence_providers():
    manager = ContextManager()

    assert manager.intelligence_broker.providers == []
    assert WorkspaceIntelligenceBroker().providers == []


def test_context_manager_does_not_synthesize_a_mode():
    session = SessionReadView(
        session_id="session-mode-free",
        started_at="",
        messages=(),
        turns=(),
        workflow_state={},
        compact_boundaries=(),
        compacted_history=(),
        content_replacements=(),
        latest_context_snapshot={},
    )

    result = ContextManager().build_messages(session)

    assert result.policy.mode_name == ""


def test_application_record_without_runtime_contribution_fails_closed():
    registry = AgentApplicationRegistry(
        application_records=(
            AgentApplicationRecord(
                application_id="app.missing-runtime",
                label="Missing runtime",
                profile_id="",
                application_state_factory=None,
                runtime_factory=None,
            ),
        ),
        default_application_id="app.missing-runtime",
    )

    with tempfile.TemporaryDirectory() as workspace:
        with pytest.raises(ApplicationConfigurationError):
            build_agent_application(
                "app.missing-runtime", ToolRuntime(workspace), registry=registry
            )


def test_inprocess_adapter_requires_selected_application_contribution():
    with tempfile.TemporaryDirectory() as workspace:
        with pytest.raises(ApplicationConfigurationError):
            InProcessAdapter(tools=ToolRuntime(workspace))


def test_inprocess_adapter_requires_explicit_model_and_tool_providers():
    with tempfile.TemporaryDirectory() as workspace:
        registry = base_agent_application_registry()
        with pytest.raises(ApplicationConfigurationError):
            InProcessAdapter(
                tools=ToolRuntime(workspace),
                agent_application_id="embedagent.generic",
                agent_application_registry=registry,
            )
        with pytest.raises(ApplicationConfigurationError):
            InProcessAdapter(
                client=object(),
                agent_application_id="embedagent.generic",
                agent_application_registry=registry,
            )


def test_missing_application_is_classified_as_configuration_failure():
    failure = failure_for_exception(
        ApplicationConfigurationError("selected application contribution is required"),
        source="host",
    )

    assert failure.code == "configuration_error"
    assert failure.source == "host"


def test_runtime_contribution_without_profile_does_not_synthesize_one():
    contribution = ApplicationRuntimeContribution(
        application_id="app.runtime-only",
        label="Runtime only",
        runtime_definition_factory=_valid_runtime_definition,
        application_state_factory=lambda: object(),
    )
    registry = application_registry_from_runtime_contributions((contribution,))

    assert registry.record_by_id("app.runtime-only").profile_id == ""
    assert callable(registry.record_by_id("app.runtime-only").application_state_factory)
    with tempfile.TemporaryDirectory() as workspace:
        application = build_agent_application(
            "app.runtime-only", ToolRuntime(workspace), registry=registry
        )

    assert application.profile is None
    assert application.runtime_definition is not None


@pytest.mark.parametrize(
    "helper",
    (
        available_agent_application_manifests,
        generic_agent_application_manifest,
        python_agent_application_manifest,
        html_agent_application_manifest,
    ),
)
def test_manifest_helpers_require_an_explicit_registry(helper):
    with pytest.raises(ApplicationConfigurationError):
        helper()


def _registry_for_factories(runtime_factory, state_factory=None, detector_factory=None):
    return AgentApplicationRegistry(
        application_records=(
            AgentApplicationRecord(
                application_id="app.factory-test",
                label="Factory test",
                profile_id="",
                application_state_factory=state_factory,
                runtime_factory=runtime_factory,
                workspace_profile_detectors_factory=detector_factory,
            ),
        ),
        default_application_id="app.factory-test",
    )


def _valid_runtime_definition():
    return RuntimeDefinition(
        application_policy=ApplicationRuntimePolicy(
            default_mode="explore",
            mode_runtime_policy=PassThroughModeRuntimePolicy("explore"),
        )
    )


def _application_for_definition(definition, application_id="app.direct"):
    return type(
        "DirectApplication",
        (),
        {
            "application_id": application_id,
            "profile": None,
            "runtime_definition": definition,
            "extension_manager": ExtensionManager(),
            "workspace_profile_detectors": (),
        },
    )()


class _CallableModeRuntimePolicy(object):
    def __init__(self, default_result="explore", mode_result=None):
        self.default_result = default_result
        self.mode_result = {"slug": "explore"} if mode_result is None else mode_result

    def default_mode(self):
        if isinstance(self.default_result, Exception):
            raise self.default_result
        return self.default_result

    def require_mode(self, mode_name):
        del mode_name
        if isinstance(self.mode_result, Exception):
            raise self.mode_result
        return self.mode_result

    def build_system_prompt(self, mode_name, app_config=None, workspace="", local_resources=None):
        del mode_name, app_config, workspace, local_resources
        return ""

    def parse_mode_switch_request(self, user_text, fallback_mode):
        return fallback_mode, user_text, False


@pytest.mark.parametrize("factory_kind", ("runtime", "state", "detector"))
def test_application_factory_failures_are_typed_configuration_errors(factory_kind):
    def fail():
        raise RuntimeError("factory failed")

    runtime_factory = fail if factory_kind == "runtime" else _valid_runtime_definition
    state_factory = fail if factory_kind == "state" else None
    detector_factory = fail if factory_kind == "detector" else None
    registry = _registry_for_factories(
        runtime_factory,
        state_factory=state_factory,
        detector_factory=detector_factory,
    )

    with tempfile.TemporaryDirectory() as workspace:
        with pytest.raises(ApplicationConfigurationError):
            build_agent_application("app.factory-test", ToolRuntime(workspace), registry=registry)


@pytest.mark.parametrize(
    "application_policy",
    (
        None,
        ApplicationRuntimePolicy(mode_tool_policy=None),
        ApplicationRuntimePolicy(write_path_policy=None),
        ApplicationRuntimePolicy(mode_runtime_policy=None),
    ),
)
def test_malformed_runtime_policy_fails_before_adapter_dereference(application_policy):
    definition = RuntimeDefinition(application_policy=application_policy)
    application = type(
        "MalformedApplication",
        (),
        {
            "application_id": "app.malformed",
            "profile": None,
            "runtime_definition": definition,
            "extension_manager": ExtensionManager(),
            "workspace_profile_detectors": (),
        },
    )()

    with tempfile.TemporaryDirectory() as workspace:
        with pytest.raises(ApplicationConfigurationError):
            InProcessAdapter(
                client=object(),
                tools=ToolRuntime(workspace),
                agent_application=application,
            )


@pytest.mark.parametrize("default_mode", ("", " ", None, 1))
def test_invalid_application_default_mode_is_a_configuration_failure(default_mode):
    definition = RuntimeDefinition(
        application_policy=ApplicationRuntimePolicy(
            default_mode=default_mode,
            mode_runtime_policy=PassThroughModeRuntimePolicy("explore"),
        )
    )
    application = type(
        "InvalidDefaultModeApplication",
        (),
        {
            "application_id": "app.invalid-default-mode",
            "profile": None,
            "runtime_definition": definition,
            "extension_manager": ExtensionManager(),
            "workspace_profile_detectors": (),
        },
    )()

    with tempfile.TemporaryDirectory() as workspace:
        with pytest.raises(ApplicationConfigurationError) as captured:
            InProcessAdapter(
                client=object(),
                tools=ToolRuntime(workspace),
                agent_application=application,
            )

    failure = failure_for_exception(captured.value, source="host")
    assert failure.code == "configuration_error"
    assert failure.retryable is False


@pytest.mark.parametrize("application_id", ("", " "))
def test_direct_application_requires_nonempty_identity(application_id):
    application = _application_for_definition(
        _valid_runtime_definition(),
        application_id=application_id,
    )

    with tempfile.TemporaryDirectory() as workspace:
        with pytest.raises(ApplicationConfigurationError) as captured:
            InProcessAdapter(
                client=object(),
                tools=ToolRuntime(workspace),
                agent_application=application,
            )

    assert failure_for_exception(captured.value, source="host").code == "configuration_error"


@pytest.mark.parametrize("application_id", ("", " "))
def test_runtime_contribution_requires_typed_nonempty_identity(application_id):
    with pytest.raises(ApplicationConfigurationError) as captured:
        ApplicationRuntimeContribution(
            application_id=application_id,
            label="Invalid identity",
            runtime_definition_factory=_valid_runtime_definition,
        )

    assert failure_for_exception(captured.value, source="host").code == "configuration_error"


@pytest.mark.parametrize(
    "mode_policy",
    (
        _CallableModeRuntimePolicy(default_result=RuntimeError("default failed")),
        _CallableModeRuntimePolicy(default_result=""),
        _CallableModeRuntimePolicy(default_result=1),
        _CallableModeRuntimePolicy(default_result="build"),
        _CallableModeRuntimePolicy(mode_result=RuntimeError("resolution failed")),
        _CallableModeRuntimePolicy(mode_result=False),
        _CallableModeRuntimePolicy(mode_result={}),
        _CallableModeRuntimePolicy(mode_result={"slug": " "}),
        _CallableModeRuntimePolicy(mode_result={"slug": "build"}),
    ),
)
def test_invalid_callable_mode_policy_is_a_configuration_failure(mode_policy):
    definition = RuntimeDefinition(
        application_policy=ApplicationRuntimePolicy(
            default_mode="explore",
            mode_runtime_policy=mode_policy,
        )
    )
    application = _application_for_definition(definition)

    with tempfile.TemporaryDirectory() as workspace:
        with pytest.raises(ApplicationConfigurationError) as captured:
            InProcessAdapter(
                client=object(),
                tools=ToolRuntime(workspace),
                agent_application=application,
            )

    failure = failure_for_exception(captured.value, source="host")
    assert failure.code == "configuration_error"
    assert failure.retryable is False


@pytest.mark.parametrize("application_id", ("", "missing.application"))
def test_empty_or_unknown_application_selection_is_a_configuration_failure(application_id):
    registry = base_agent_application_registry()

    with pytest.raises(ApplicationConfigurationError) as captured:
        registry.record_by_id(application_id)

    failure = failure_for_exception(captured.value, source="host")
    assert failure.code == "configuration_error"
    assert failure.retryable is False


def test_generic_host_sources_have_no_mode_profile_or_provider_fallbacks():
    host_source = (
        __import__("pathlib").Path(__file__).parents[1]
        / "packages"
        / "embedagent-host"
        / "src"
        / "embedagent_host"
    )
    adapter_source = (host_source / "inprocess_adapter.py").read_text(encoding="utf-8")
    context_source = (host_source / "runtime" / "context.py").read_text(encoding="utf-8")
    application_source = (host_source / "runtime" / "agent_applications.py").read_text(
        encoding="utf-8"
    )
    product_source = (
        __import__("pathlib").Path(__file__).parents[1]
        / "src"
        / "embedagent"
        / "product_catalog.py"
    ).read_text(encoding="utf-8")

    assert "base_agent_application_registry" not in adapter_source
    assert 'model="default-model"' not in adapter_source
    assert "OpenAICompatibleClient(" not in adapter_source
    assert "WorkspaceIntelligenceBroker.default()" not in context_source
    assert 'or "build"' not in context_source
    assert "_runtime_definition_for_profile" not in application_source
    assert "_registry_or_base" not in application_source
    assert "AgentProfileRuntimePolicy" not in adapter_source
    assert "runtime_contribution_for_record" in product_source
    assert "application_registry_from_runtime_contributions" in product_source
