import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]


def _load_validator():
    script = ROOT / "scripts" / "validate-release-evidence.py"
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location("phase7_evidence_validator", str(script))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def test_runtime_contract_versions_target_evidence():
    contract = json.loads((ROOT / "scripts" / "offline-runtime-contract.json").read_text())
    gate = next(
        item for item in contract["release_gates"] if item["id"] == "win7_windowed_gui_smoke"
    )

    assert contract["win7_evidence_schema_version"] == 1
    assert gate["report_schema_version"] == 1
    assert gate["manual_on_win7"] is True


def test_target_schema_requires_hash_bound_win7_results():
    schema = json.loads((ROOT / "scripts" / "target-report.schema.json").read_text())

    assert schema["properties"]["release_identity_sha256"]
    assert schema["properties"]["bundle_plan_sha256"]
    assert "gate_ids" in schema["required"]
    assert "gate_results" in schema["required"]
    assert schema["properties"]["command_exit_codes"]
    conditional_requirements = [item["then"]["required"] for item in schema["allOf"]]
    assert ["webview2", "gui"] in conditional_requirements
    assert ["cpp_smoke"] in conditional_requirements


def test_validator_accepts_complete_structured_target_report():
    validator = _load_validator()
    gate_ids = [
        "cpp_smoke_workspace",
        "gui_headless_smoke",
        "runtime_contract",
        "win7_cli_smoke",
        "win7_windowed_gui_smoke",
    ]
    identity = {
        "schema_version": 2,
        "source_revision": "abc",
        "version": "0.1.0",
        "flavor_id": "cpp-desktop",
        "target_id": "win7-x64-portable",
        "bundle_plan_sha256": "e" * 64,
        "agent_lock_sha256": "f" * 64,
        "gate_ids": gate_ids,
    }
    report = {
        "schema_version": 1,
        "release_identity_sha256": validator.identity_sha256(identity),
        "bundle_plan_sha256": identity["bundle_plan_sha256"],
        "gate_ids": gate_ids,
        "gate_results": {
            gate_id: {
                "ok": True,
                **({} if gate_id == "runtime_contract" else {"runtime_source": "bundle"}),
            }
            for gate_id in gate_ids
        },
        "machine": {
            "os": "Microsoft Windows 7",
            "service_pack": "SP1",
            "architecture": "AMD64",
        },
        "webview2": {
            "major": 109,
            "runtime_source": "bundle",
            "fixed_runtime_exists": True,
        },
        "gui": {"renderer": "edgechromium", "windowed_smoke": "passed"},
        "cpp_smoke": {
            "ok": True,
            "runtime_source": "bundle",
            "system_tool_fallback": False,
        },
        "command_exit_codes": {"gui": 0, "cpp": 0},
        "blocking_errors": [],
    }

    result = validator.validate_report(identity, report)

    assert result["status"] == "ACCEPTED"
    assert result["blocking_errors"] == []


def test_bundle_scripts_ship_the_evidence_kit():
    prepare = (ROOT / "scripts" / "prepare-offline.ps1").read_text(encoding="utf-8")
    build = (ROOT / "scripts" / "build-offline-bundle.ps1").read_text(encoding="utf-8")

    for marker in ("validate-release-evidence.py", "win7-runbook.md"):
        assert marker in prepare
    for marker in ("expected-bundle-hashes.json", "target-report.schema.json"):
        assert marker in build
