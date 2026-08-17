from __future__ import annotations

import sys

import pytest
from embedagent_composition import ApplicationManifest
from embedagent_host.runtime.agent_applications import application_descriptor_payload
from embedagent_host.runtime.profiles import generic_agent_profile
from embedagent_host.runtime.workspace_intelligence import WorkspaceIntelligenceBroker
from embedagent_workflow_cpp.application import cpp_application_manifest

from embedagent.application_loader import (
    bootstrap_generic_shell,
    compile_generic_shell_descriptor,
)


class RecordingRegistrar(object):
    def __init__(self):
        self.entries = []
        self.active = []

    def add_shell_contribution(self, contribution, source_id):
        self.entries.append(source_id)
        self.active.append(source_id)
        return lambda: self.active.remove(source_id)

    def dispose(self):
        self.active[:] = []


def test_generic_bootstrap_imports_only_the_plan_registration_entry():
    plan = {
        "allowed_agent_application_ids": ["embedagent.generic"],
        "registration_entries": ["embedagent.product_catalog:register"],
    }
    registrar = RecordingRegistrar()
    sys.modules.pop("embedagent_workflow_cpp", None)
    disposer = bootstrap_generic_shell(plan, registrar)
    assert registrar.entries == ["embedagent.product_catalog"]
    assert "embedagent_workflow_cpp" not in sys.modules
    disposer()
    assert registrar.active == []


def test_generic_shell_descriptor_has_no_application_specific_commands():
    plan = {"allowed_agent_application_ids": ["embedagent.generic"]}
    descriptor = compile_generic_shell_descriptor(plan, {})
    assert all(not item.id.startswith("workflow.") for item in descriptor.commands)


def test_loader_rejects_unsafe_registration_entry_before_import():
    from embedagent.application_loader import load_selected_applications

    with pytest.raises(ValueError, match="application_registration_error"):
        load_selected_applications(
            {"registration_entries": ["../untrusted:register"]},
            RecordingRegistrar(),
        )


def test_loader_disposes_registrar_when_registration_callback_fails(monkeypatch):
    from embedagent.application_loader import load_selected_applications

    registrar = RecordingRegistrar()

    def fail_register(registrar):
        registrar.add_shell_contribution(object(), "tests.failed")
        raise RuntimeError("registration failed")

    monkeypatch.setattr("embedagent.application_loader._load_entry", lambda entry: fail_register)
    with pytest.raises(ValueError, match="application_registration_error"):
        load_selected_applications(
            {"registration_entries": ["tests.failed:register"]},
            registrar,
        )
    assert registrar.active == []


def test_application_descriptor_does_not_synthesize_modes():
    manifest = ApplicationManifest(
        application_id="app.generic",
        version="0.1.0",
        api_version="agent_application_v1",
        distribution_id="embedagent-shell",
        registration_entry="embedagent.product_catalog:register",
    )
    payload = application_descriptor_payload(manifest, active=True)
    assert payload["capabilities"] == []
    assert "modes" not in payload


def test_cpp_descriptor_exposes_modes_only_when_selected():
    payload = application_descriptor_payload(cpp_application_manifest(), active=True)
    assert {"mode.explore", "mode.build"}.issubset(set(payload["capabilities"]))


def test_generic_profile_does_not_project_platform_modes():
    assert generic_agent_profile().mode_descriptor_payloads() == []


def test_workspace_intelligence_has_no_implicit_providers():
    assert WorkspaceIntelligenceBroker().providers == []
