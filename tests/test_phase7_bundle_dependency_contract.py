import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "scripts" / "check-bundle-dependencies.py"
RUNTIME_CONTRACT = ROOT / "scripts" / "offline-runtime-contract.json"
VALIDATOR_PATH = ROOT / "scripts" / "validate-offline-bundle.ps1"


def _load_checker():
    spec = importlib.util.spec_from_file_location("bundle_dependency_checker", str(CHECKER_PATH))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _powershell_exe():
    candidates = (
        Path(r"C:\Program Files\PowerShell\7\pwsh.exe"),
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe",
    )
    return next(str(candidate) for candidate in candidates if candidate.exists())


def _stage_path(bundle_root, relative_path):
    target = bundle_root.joinpath(*relative_path.replace("\\", "/").split("/"))
    if target.suffix:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fixture", encoding="ascii")
    else:
        target.mkdir(parents=True, exist_ok=True)
    return target


def _compile_plan(tmp_path, flavor):
    output_dir = tmp_path / ("plan-" + flavor)
    report_path = tmp_path / ("plan-" + flavor + "-report.json")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "compile-bundle-plan.py"),
            "--flavor",
            flavor,
            "--target",
            "win7-x64-portable",
            "--assurance",
            "release",
            "--runtime-contract",
            str(RUNTIME_CONTRACT),
            "--asset-manifest",
            str(ROOT / "scripts" / "offline-assets.json"),
            "--output-dir",
            str(output_dir),
            "--json-report",
            str(report_path),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return output_dir


def _write_valid_bundle(tmp_path, flavor="minimal-cli"):
    plan_root = _compile_plan(tmp_path, flavor)
    bundle_root = tmp_path / ("bundle-" + flavor)
    manifest_root = bundle_root / "manifests"
    manifest_root.mkdir(parents=True)
    for name in ("bundle-plan.json", "agent.json", "agent.lock.json"):
        (manifest_root / name).write_bytes((plan_root / name).read_bytes())
    plan_path = manifest_root / "bundle-plan.json"
    plan = json.loads(plan_path.read_text(encoding="ascii"))
    plan_hash = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    contract = json.loads(RUNTIME_CONTRACT.read_text(encoding="utf-8"))
    components = {item["id"]: item for item in contract["runtime_components"]}
    launchers = {item["id"]: item for item in contract["launchers"]}
    gates = {item["id"]: item for item in contract["release_gates"]}

    for component_id in plan["runtime_component_ids"]:
        component = components[component_id]
        for relative_path in component.get("paths", ()):
            _stage_path(bundle_root, relative_path)
        for tool in component.get("managed_tools", ()):
            for relative_path in tool.get("paths", ()):
                _stage_path(bundle_root, relative_path)
            alternatives = tool.get("alternatives") or ()
            if alternatives:
                for relative_path in alternatives[0].get("paths", ()):
                    _stage_path(bundle_root, relative_path)
            for child in tool.get("children", ()):
                _stage_path(bundle_root, child["path"])
    for launcher_id in plan["launcher_ids"]:
        _stage_path(bundle_root, launchers[launcher_id]["path"])
    for gate_id in plan["gate_ids"]:
        gate = gates[gate_id]
        for field in ("script", "workspace", "launcher"):
            if gate.get(field):
                _stage_path(bundle_root, gate[field])

    if "gui" in plan["shell_ids"]:
        _stage_path(bundle_root, "app/embedagent/frontend/gui/static/index.html")
        _stage_path(bundle_root, "app/embedagent/frontend/gui/static/assets/app.js")
        _stage_path(bundle_root, "runtime/webview2-fixed-runtime/msedgewebview2.exe")

    feature_packages = {
        "tui": ("prompt_toolkit", "rich", "pygments", "wcwidth"),
        "gui": (
            "webview",
            "fastapi",
            "uvicorn",
            "websockets",
            "starlette",
            "pydantic",
            "anyio",
            "sniffio",
            "h11",
            "idna",
            "click",
            "typing_extensions",
            "colorama",
        ),
    }
    for feature_id in plan["python_feature_ids"]:
        for package in feature_packages[feature_id]:
            _stage_path(bundle_root, "runtime/site-packages/" + package)

    manifest = {
        "schema_version": 2,
        "artifact_name": plan["artifact_name"],
        "flavor_id": plan["flavor_id"],
        "bundle_plan_sha256": plan_hash,
        "agent_lock_sha256": plan["agent_lock_sha256"],
        "allowed_agent_application_ids": plan["allowed_agent_application_ids"],
        "shell_ids": plan["shell_ids"],
        "runtime_component_ids": plan["runtime_component_ids"],
        "resolved_asset_ids": plan["asset_ids"],
        "python_feature_ids": plan["python_feature_ids"],
        "staged_launcher_ids": plan["launcher_ids"],
        "gate_ids": plan["gate_ids"],
        "components": [],
    }
    (manifest_root / "bundle-manifest.json").write_text(json.dumps(manifest), encoding="ascii")
    return bundle_root


def test_dependency_checker_accepts_product_only_in_app_tree():
    script = CHECKER_PATH.read_text(encoding="utf-8")

    assert "Product code is intentionally staged under app/embedagent" in script
    assert "Manifest source_mode must be wheel-installed" in script
    assert "Manifest project_wheels must contain the exact six project wheels" in script
    assert "Duplicate product import package" in script


@pytest.mark.parametrize(
    "unexpected_path",
    (
        "embedagent-gui.cmd",
        "runtime/webview2-fixed-runtime/msedgewebview2.exe",
        "bin/llvm/bin/clang.exe",
        "data/workspace-template/main.c",
    ),
)
def test_minimal_bundle_rejects_unplanned_runtime_content(tmp_path, unexpected_path):
    checker = _load_checker()
    bundle = _write_valid_bundle(tmp_path)
    _stage_path(bundle, unexpected_path)

    ok, errors = checker.validate_against_plan(bundle)

    assert not ok
    assert any("unplanned" in item.lower() for item in errors)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only PowerShell validator")
@pytest.mark.parametrize(
    "unexpected_path",
    (
        "embedagent-gui.cmd",
        "runtime/webview2-fixed-runtime/msedgewebview2.exe",
        "bin/llvm/bin/clang.exe",
        "data/workspace-template/main.c",
    ),
)
def test_powershell_validator_rejects_unplanned_runtime_content(tmp_path, unexpected_path):
    bundle = _write_valid_bundle(tmp_path)
    _stage_path(bundle, unexpected_path)
    sources = tmp_path / "sources"
    sources.mkdir()
    report_path = tmp_path / "validate-report.json"
    result = subprocess.run(
        [
            _powershell_exe(),
            "-NoProfile",
            "-File",
            str(VALIDATOR_PATH),
            "-BundleRoot",
            str(bundle),
            "-SourcesRoot",
            str(sources),
            "-ZipPath",
            str(tmp_path / "bundle.zip"),
            "-SkipDynamicChecks",
            "-RequireComplete",
            "-JsonOutputPath",
            str(report_path),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode != 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    unplanned = [item for item in payload["results"] if item["code"] == "bundle.plan.unplanned"]
    assert any(
        unexpected_path.split("/")[0].lower() in item["message"].lower() for item in unplanned
    )


def test_bundle_rejects_plan_hash_mismatch(tmp_path):
    checker = _load_checker()
    bundle = _write_valid_bundle(tmp_path)
    manifest_path = bundle / "manifests" / "bundle-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    manifest["bundle_plan_sha256"] = "f" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="ascii")

    ok, errors = checker.validate_against_plan(bundle)

    assert not ok
    assert any("hash mismatch" in item.lower() for item in errors)


def test_bundle_rejects_missing_selected_launcher(tmp_path):
    checker = _load_checker()
    bundle = _write_valid_bundle(tmp_path)
    (bundle / "embedagent.cmd").unlink()

    ok, errors = checker.validate_against_plan(bundle)

    assert not ok
    assert any("selected launcher" in item.lower() for item in errors)


def test_bundle_rejects_missing_selected_python_feature_dependency(tmp_path):
    checker = _load_checker()
    bundle = _write_valid_bundle(tmp_path, "cpp-desktop")
    (bundle / "runtime" / "site-packages" / "prompt_toolkit").rmdir()

    ok, errors = checker.validate_against_plan(bundle)

    assert not ok
    assert any("prompt_toolkit" in item for item in errors)


def test_bundle_rejects_extra_manifest_gate(tmp_path):
    checker = _load_checker()
    bundle = _write_valid_bundle(tmp_path)
    manifest_path = bundle / "manifests" / "bundle-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    manifest["gate_ids"].append("gui_headless_smoke")
    manifest_path.write_text(json.dumps(manifest), encoding="ascii")

    ok, errors = checker.validate_against_plan(bundle)

    assert not ok
    assert any("gate_ids" in item for item in errors)
