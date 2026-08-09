import json
from pathlib import Path

from embedagent_composition import compile_bundle_plan

from embedagent.bundle_catalog import (
    official_bundle_recipe_registry,
    product_component_catalog,
)

ROOT = Path(__file__).resolve().parents[1]


def _compile(flavor):
    contract = json.loads(
        (ROOT / "scripts" / "offline-runtime-contract.json").read_text(encoding="utf-8")
    )
    assets = json.loads((ROOT / "scripts" / "offline-assets.json").read_text(encoding="utf-8"))
    return compile_bundle_plan(
        recipe=official_bundle_recipe_registry().resolve(flavor),
        catalog=product_component_catalog(),
        runtime_contract=contract,
        asset_manifest=assets,
        target_id="win7-x64-portable",
        assurance="release",
    )


def test_minimal_cli_excludes_cpp_gui_and_desktop_gates():
    plan = _compile("minimal-cli")
    assert plan.shell_ids == ("cli",)
    assert plan.allowed_agent_application_ids == ("embedagent.generic",)
    assert "renderer.webview2" not in plan.runtime_capability_ids
    assert "toolchain.clang" not in plan.runtime_capability_ids
    assert "gui" not in plan.python_feature_ids
    assert "tui" not in plan.python_feature_ids
    assert "gui_headless_smoke" not in plan.gate_ids
    assert "cpp_smoke_workspace" not in plan.gate_ids
    assert plan.gate_ids == ("runtime_contract", "win7_cli_smoke")


def test_cpp_desktop_preserves_full_runtime_and_gates():
    plan = _compile("cpp-desktop")
    assert plan.shell_ids == ("cli", "tui", "gui")
    assert plan.allowed_agent_application_ids == ("embedagent.default_c_cpp",)
    assert "renderer.webview2" in plan.runtime_capability_ids
    assert "toolchain.clang" in plan.runtime_capability_ids
    assert plan.python_feature_ids == ("gui", "tui")
    assert set(plan.gate_ids) == {
        "runtime_contract",
        "win7_cli_smoke",
        "cpp_smoke_workspace",
        "gui_headless_smoke",
        "win7_windowed_gui_smoke",
    }


def test_official_configuration_templates_are_credential_free():
    expected_applications = {
        "minimal-cli": "embedagent.generic",
        "cpp-desktop": "embedagent.default_c_cpp",
    }
    for template_id, application_id in expected_applications.items():
        path = ROOT / "config" / "bundle-flavors" / (template_id + ".json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["agent_application_id"] == application_id
        assert "api_key" not in payload
