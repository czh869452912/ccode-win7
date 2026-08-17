from __future__ import annotations

from embedagent_core import ApplicationRegistrar
from embedagent_workflow_cpp.application import (
    cpp_application_manifest,
    register_application,
)


class RecordingApplicationRegistrar(object):
    def __init__(self):
        self.source_ids = []
        self.active_source_ids = []
        self.runtime_contributions = []

    def _record(self, source_id):
        self.source_ids.append(source_id)
        self.active_source_ids.append(source_id)
        return lambda: self.active_source_ids.remove(source_id)

    def add_extension(self, extension, source_id):
        return self._record(source_id)

    def add_prompt_provider(self, provider, source_id):
        return self._record(source_id)

    def add_context_provider(self, provider, source_id):
        return self._record(source_id)

    def add_shell_contribution(self, contribution, source_id):
        return self._record(source_id)

    def add_runtime_contribution(self, contribution, source_id):
        self.runtime_contributions.append(contribution)
        return lambda: self.runtime_contributions.remove(contribution)


def test_cpp_plugin_manifest_declares_only_public_dependencies():
    manifest = cpp_application_manifest()
    assert manifest.distribution_id == "embedagent-workflow-cpp"
    assert manifest.registration_entry.endswith(":register_application")
    assert "embedagent" not in manifest.requires
    assert "toolchain.clang" in manifest.runtime_requirements


def test_cpp_registration_is_disposable():
    registrar = RecordingApplicationRegistrar()
    disposer = register_application(registrar)
    assert registrar.source_ids == [
        "embedagent.workflow.cpp",
        "embedagent.workflow.cpp",
        "embedagent.workflow.cpp",
        "embedagent.workflow.cpp",
    ]
    disposer()
    assert registrar.active_source_ids == []


def test_cpp_registration_declares_runtime_contribution_without_host_dependency():
    registrar = RecordingApplicationRegistrar()
    disposer = register_application(registrar)
    assert [item.application_id for item in registrar.runtime_contributions] == [
        "embedagent.default_c_cpp"
    ]
    disposer()
    assert registrar.runtime_contributions == []


def test_cpp_registration_works_with_core_registrar_and_is_idempotent():
    calls = []

    class ExtensionHost(object):
        def register(self, extension, source_id):
            return lambda: calls.append(("extension", source_id))

        def register_prompt_provider(self, provider, source_id):
            return lambda: calls.append(("prompt", source_id))

        def register_context_provider(self, provider, source_id):
            return lambda: calls.append(("context", source_id))

    class ShellRegistry(object):
        def register(self, contribution, source_id):
            return lambda: calls.append(("shell", source_id))

    class RuntimeRegistry(object):
        def register(self, contribution, source_id):
            return lambda: calls.append(("runtime", source_id))

    registrar = ApplicationRegistrar(ExtensionHost(), ShellRegistry(), RuntimeRegistry())
    disposer = register_application(registrar)

    assert callable(disposer)
    disposer()
    registrar.dispose()
    assert calls == [
        ("shell", "embedagent.workflow.cpp"),
        ("context", "embedagent.workflow.cpp"),
        ("prompt", "embedagent.workflow.cpp"),
        ("extension", "embedagent.workflow.cpp"),
        ("runtime", "embedagent.workflow.cpp"),
    ]
