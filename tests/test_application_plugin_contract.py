from __future__ import annotations

import embedagent_composition
import embedagent_core
import pytest


def _manifest(**overrides):
    manifest_type = getattr(embedagent_composition, "ApplicationManifest", None)
    assert manifest_type is not None, "ApplicationManifest contract is missing"
    values = {
        "application_id": "app.generic",
        "version": "0.1.0",
        "api_version": "agent_application_v1",
        "distribution_id": "embedagent-shell",
        "registration_entry": "embedagent.generic_application:register_application",
    }
    values.update(overrides)
    return manifest_type(**values)


def _validate(manifest):
    validator = getattr(embedagent_composition, "validate_application_manifest", None)
    assert validator is not None, "application manifest validator is missing"
    return validator(manifest)


class RecordingApplicationRegistrar(object):
    def __init__(self):
        self.source_ids = []
        self.active_source_ids = []
        self.runtime_contributions = []

    def add_extension(self, extension, source_id):
        self.source_ids.append(source_id)
        self.active_source_ids.append(source_id)
        return lambda: self.active_source_ids.remove(source_id)

    def add_prompt_provider(self, provider, source_id):
        return self.add_extension(provider, source_id)

    def add_context_provider(self, provider, source_id):
        return self.add_extension(provider, source_id)

    def add_shell_contribution(self, contribution, source_id):
        return self.add_extension(contribution, source_id)

    def add_runtime_contribution(self, contribution, source_id):
        self.source_ids.append(source_id)
        self.runtime_contributions.append(contribution)
        return lambda: self.runtime_contributions.remove(contribution)

    def dispose(self):
        self.active_source_ids[:] = []


def test_application_manifest_requires_explicit_registration_entry():
    manifest = _manifest(registration_entry="")
    with pytest.raises(ValueError, match="registration_entry"):
        _validate(manifest)


def test_registration_entry_must_be_module_colon_symbol():
    manifest = _manifest(registration_entry="../unsafe.py")
    with pytest.raises(ValueError, match="registration_entry"):
        _validate(manifest)


def test_manifest_permission_metadata_does_not_grant_permission():
    manifest = _manifest(capabilities=("tool.write_file",), permission_categories=("write",))
    payload = manifest.to_dict()
    assert payload["permission_categories"] == ["write"]
    assert "permission_grant" not in payload


def test_application_registrar_disposes_source_registrations_in_reverse_order():
    registrar_type = getattr(embedagent_core, "ApplicationRegistrar", None)
    assert registrar_type is not None, "ApplicationRegistrar contract is missing"
    calls = []

    class ExtensionHost(object):
        def register(self, extension, source_id):
            calls.append(("register", source_id))
            return lambda: calls.append(("dispose", source_id))

    class ShellRegistry(object):
        def register(self, contribution, source_id):
            calls.append(("register_shell", source_id))
            return lambda: calls.append(("dispose_shell", source_id))

    registrar = registrar_type(ExtensionHost(), ShellRegistry())
    registrar.add_extension(object(), "app.first")
    registrar.add_shell_contribution(object(), "app.second")
    registrar.dispose()
    registrar.dispose()
    assert calls == [
        ("register", "app.first"),
        ("register_shell", "app.second"),
        ("dispose_shell", "app.second"),
        ("dispose", "app.first"),
    ]


def test_application_runtime_contribution_is_a_focused_workflow_neutral_contract():
    contribution_type = getattr(embedagent_core, "ApplicationRuntimeContribution", None)
    assert contribution_type is not None, "runtime contribution contract is missing"
    contribution = contribution_type(
        application_id="app.generic",
        label="Generic Agent",
        runtime_definition_factory=lambda: object(),
        application_state_factory=lambda: object(),
        capabilities=("tool.read_file",),
        workflow_package_ids=("workflow.generic",),
    )
    assert contribution.application_id == "app.generic"
    assert callable(contribution.runtime_definition_factory)
    assert callable(contribution.application_state_factory)
    assert contribution.capabilities == ("tool.read_file",)
    assert contribution.workflow_package_ids == ("workflow.generic",)
    assert not hasattr(contribution, "permission_policy")


def test_application_registrar_collects_runtime_contributions_and_disposes_them():
    registrar_type = getattr(embedagent_core, "ApplicationRegistrar", None)
    contribution_type = getattr(embedagent_core, "ApplicationRuntimeContribution", None)
    assert registrar_type is not None
    assert contribution_type is not None

    class ExtensionHost(object):
        def register(self, extension, source_id):
            del extension, source_id
            return lambda: None

    class ShellRegistry(object):
        def register(self, contribution, source_id):
            del contribution, source_id
            return lambda: None

        def register_application(self, application_id):
            del application_id
            return lambda: None

    contribution = contribution_type(
        application_id="app.generic",
        label="Generic Agent",
        runtime_definition_factory=lambda: object(),
    )
    registrar = registrar_type(ExtensionHost(), ShellRegistry())
    disposer = registrar.add_runtime_contribution(contribution, "app.generic")
    assert registrar.runtime_contributions() == (contribution,)
    disposer()
    assert registrar.runtime_contributions() == ()


def test_application_registrar_rolls_back_runtime_and_shell_when_shell_registration_fails():
    registrar_type = getattr(embedagent_core, "ApplicationRegistrar", None)
    contribution_type = getattr(embedagent_core, "ApplicationRuntimeContribution", None)
    calls = []

    class ExtensionHost(object):
        def register(self, extension, source_id):
            del extension, source_id
            return lambda: None

    class RuntimeRegistry(object):
        def register(self, contribution, source_id):
            del contribution, source_id

            def dispose():
                calls.append("runtime_dispose")

            return dispose

    class ShellRegistry(object):
        def register_application(self, application_id):
            calls.append(("shell_register", application_id))
            raise RuntimeError("shell failure")

    registrar = registrar_type(ExtensionHost(), ShellRegistry(), RuntimeRegistry())
    contribution = contribution_type(
        application_id="app.failed",
        label="Failed Agent",
        runtime_definition_factory=lambda: object(),
    )

    with pytest.raises(RuntimeError, match="shell failure"):
        registrar.add_runtime_contribution(contribution, "app.failed")
    assert registrar.runtime_contributions() == ()
    assert calls == [
        ("shell_register", "app.failed"),
        "runtime_dispose",
    ]
