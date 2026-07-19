import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate-release-evidence.py"


def _load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location("release_evidence_test_module", str(SCRIPT))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


@pytest.fixture
def identity():
    return {
        "schema_version": 1,
        "source_revision": "abc123",
        "version": "0.1.0",
        "profile": "release",
        "project_distributions": [
            "embedagent-core",
            "embedagent-protocol",
            "embedagent-host",
            "embedagent-composition",
            "embedagent-workflow-cpp",
            "embedagent",
        ],
        "wheels": [],
    }


@pytest.fixture
def valid_report(identity):
    module = _load_module()
    return {
        "schema_version": 1,
        "release_identity_sha256": module.identity_sha256(identity),
        "machine": {
            "os_name": "Microsoft Windows 7",
            "service_pack": "SP1",
            "architecture": "AMD64",
        },
        "gui": {
            "renderer": "edgechromium",
            "runtime_source": "bundle",
            "webview2_major": 109,
            "fixed_runtime_exists": True,
        },
        "cpp": {
            "ok": True,
            "runtime_source": "bundle",
            "allow_system_tool_fallback": False,
        },
        "blocking_errors": [],
    }


@pytest.mark.parametrize(
    "mutator,code",
    [
        (lambda report: report.pop("machine"), "machine.missing"),
        (
            lambda report: report["machine"].update(os_name="Microsoft Windows 10"),
            "machine.os_name",
        ),
        (lambda report: report["gui"].update(webview2_major=110), "gui.webview2_major"),
        (lambda report: report["gui"].update(renderer="mshtml"), "gui.renderer"),
        (lambda report: report["gui"].update(runtime_source="system"), "gui.runtime_source"),
        (lambda report: report["cpp"].update(ok=False), "cpp.ok"),
        (
            lambda report: report["cpp"].update(allow_system_tool_fallback=True),
            "cpp.system_tool_fallback",
        ),
        (lambda report: report.update(blocking_errors=["failure"]), "blocking_errors.empty"),
    ],
)
def test_validate_report_rejects_mismatches(identity, valid_report, mutator, code):
    module = _load_module()
    report = copy.deepcopy(valid_report)
    mutator(report)

    result = module.validate_report(identity, report)

    assert result["status"] == "NOT_READY"
    assert code in result["blocking_errors"]


def test_validate_report_accepts_complete_win7_report(identity, valid_report):
    module = _load_module()
    result = module.validate_report(identity, valid_report)

    assert result["status"] == "ACCEPTED"
    assert result["blocking_errors"] == []


def test_cli_writes_acceptance_report(tmp_path, identity, valid_report):
    identity_path = tmp_path / "release-identity.json"
    report_path = tmp_path / "win7-evidence.json"
    output_path = tmp_path / "acceptance-report.json"
    identity_path.write_text(json.dumps(identity), encoding="utf-8")
    report_path.write_text(json.dumps(valid_report), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--identity",
            str(identity_path),
            "--report",
            str(report_path),
            "--json-report",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "ACCEPTED"
