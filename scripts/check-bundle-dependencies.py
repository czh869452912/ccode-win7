#!/usr/bin/env python3
"""
Offline Bundle Dependency Checker
Ensures all dependencies are present for zero-dependency deployment.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "scripts" / "offline-runtime-contract.json"
for candidate in (ROOT / "src", ROOT / "app"):
    if candidate.exists():
        sys.path.insert(0, str(candidate))

from embedagent.runtime_discovery import discover_bundle_root  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(
        description="Offline Bundle Dependency Checker",
    )
    parser.add_argument(
        "bundle_root",
        nargs="?",
        default="",
        help="Bundle root path (optional, auto-detect when omitted)",
    )
    parser.add_argument(
        "--json-report",
        default="",
        help="Optional path for a machine-readable JSON report",
    )
    return parser.parse_args()


def write_json_report(path: str, payload: Dict) -> None:
    if not path:
        return
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def load_runtime_contract() -> Dict:
    with open(CONTRACT, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("runtime contract must be a JSON object")
    if not isinstance(payload.get("required_tools"), list):
        raise ValueError("runtime contract missing required_tools array")
    return payload


def runtime_contract_summary(contract: Dict) -> Dict:
    return {
        "path": str(CONTRACT),
        "schema_version": contract.get("schema_version"),
        "release_gates": [
            str(item.get("id") or "")
            for item in contract.get("release_gates") or []
            if isinstance(item, dict)
        ],
    }


def get_bundle_root() -> Optional[Path]:
    """Auto-detect bundle root when no explicit path is provided."""
    resolved = discover_bundle_root(
        anchor_path=str(Path(__file__).resolve()),
        anchor_levels=(1,),
        extra_candidates=(str(Path.cwd()),),
    )
    if not resolved:
        return None
    return Path(resolved)


def check_python_runtime(bundle_root: Path) -> Tuple[bool, List[str]]:
    """Check Python runtime exists."""
    errors = []
    python_exe = bundle_root / "runtime" / "python" / "python.exe"

    if not python_exe.exists():
        errors.append("Missing: runtime/python/python.exe")

    return len(errors) == 0, errors


def check_site_packages(bundle_root: Path) -> Tuple[bool, List[str]]:
    """Check all required Python packages are present."""
    errors = []
    sp = bundle_root / "runtime" / "site-packages"

    if not sp.exists():
        errors.append("Missing: runtime/site-packages directory")
        return False, errors

    product_import_root = bundle_root / "app" / "embedagent"
    if not product_import_root.is_dir():
        errors.append("Missing product import package: app/embedagent")
    if (sp / "embedagent").is_dir():
        errors.append(
            "Duplicate product import package: "
            "runtime/site-packages/embedagent; use app/embedagent only"
        )
    project_packages = (
        ("embedagent", "", "embedagent-0.1.0.dist-info"),
        ("embedagent_core", "embedagent_core", "embedagent_core-0.1.0.dist-info"),
        (
            "embedagent_protocol",
            "embedagent_protocol",
            "embedagent_protocol-0.1.0.dist-info",
        ),
        ("embedagent_host", "embedagent_host", "embedagent_host-0.1.0.dist-info"),
        (
            "embedagent_composition",
            "embedagent_composition",
            "embedagent_composition-0.1.0.dist-info",
        ),
        (
            "embedagent_workflow_cpp",
            "embedagent_workflow_cpp",
            "embedagent_workflow_cpp-0.1.0.dist-info",
        ),
    )
    for display_name, import_name, dist_info_name in project_packages:
        if import_name and not (sp / import_name).is_dir():
            errors.append("Missing project import package: %s" % display_name)
        if not (sp / dist_info_name / "METADATA").is_file():
            errors.append("Missing project distribution metadata: %s" % dist_info_name)

    # Third-party packages that must be present
    critical = {
        # TUI
        "prompt_toolkit": ["prompt_toolkit", "prompt-toolkit"],
        "rich": ["rich"],
        # GUI
        "webview": ["webview", "pywebview"],
        "fastapi": ["fastapi"],
        "uvicorn": ["uvicorn"],
        "websockets": ["websockets"],
        # FastAPI deps
        "starlette": ["starlette"],
        "pydantic": ["pydantic", "pydantic_core"],
        "anyio": ["anyio"],
        "sniffio": ["sniffio"],
        # HTTP
        "h11": ["h11"],
        "idna": ["idna"],
        # Utils
        "click": ["click"],
        "typing_extensions": ["typing_extensions", "typing-extensions"],
        "colorama": ["colorama"],
        "pygments": ["pygments", "Pygments"],
        "wcwidth": ["wcwidth"],
    }

    for display_name, variants in critical.items():
        found = False
        for variant in variants:
            if (sp / variant).exists():
                found = True
                break
            if (sp / f"{variant}.py").exists():
                found = True
                break
            if list(sp.glob(f"{variant}-*.dist-info")):
                found = True
                break
            if list(sp.glob(f"{variant}_*.pyd")) or list(sp.glob(f"{variant}*.so")):
                found = True
                break

        if not found:
            errors.append(f"Missing package: {display_name}")

    # Check package count
    pkg_count = len([d for d in sp.iterdir() if d.is_dir() and not d.name.endswith(".dist-info")])
    if pkg_count < 20:  # Minimum expected packages
        errors.append(f"Warning: Only {pkg_count} packages found, expected at least 20")

    editable_links = list(sp.glob("__editable__*.pth"))
    if editable_links:
        names = ", ".join(item.name for item in editable_links)
        errors.append(f"Editable path links should not be bundled: {names}")

    return len(errors) == 0, errors


def _paths_exist(bundle_root: Path, paths: List[str]) -> bool:
    for relative_path in paths:
        if not bundle_root.joinpath(
            *str(relative_path or "").replace("\\", "/").split("/")
        ).exists():
            return False
    return True


def _alternative_exists(bundle_root: Path, alternatives: List[Dict]) -> bool:
    for alternative in alternatives:
        paths = alternative.get("paths") if isinstance(alternative, dict) else []
        if _paths_exist(bundle_root, list(paths or [])):
            return True
    return False


def _contract_path(bundle_root: Path, relative_path: str) -> Path:
    return bundle_root.joinpath(*str(relative_path or "").replace("\\", "/").split("/"))


def check_external_tools(bundle_root: Path) -> Tuple[bool, List[str]]:
    """Check external binary tools."""
    errors = []
    contract = load_runtime_contract()

    for tool in contract.get("required_tools") or []:
        if not isinstance(tool, dict):
            continue
        tool_id = str(tool.get("id") or "")
        alternatives = tool.get("alternatives")
        if isinstance(alternatives, list):
            if not _alternative_exists(bundle_root, alternatives):
                errors.append("runtime_tool.%s missing: alternatives not found" % tool_id)
        elif not _paths_exist(bundle_root, list(tool.get("paths") or [])):
            errors.append("runtime_tool.%s missing: required paths not found" % tool_id)

        for child in tool.get("children") or []:
            if not isinstance(child, dict):
                continue
            child_id = str(child.get("id") or "")
            child_path = str(child.get("path") or "")
            if child_path and not _contract_path(bundle_root, child_path).exists():
                errors.append("runtime_tool.%s.%s missing: %s" % (tool_id, child_id, child_path))

    return len(errors) == 0, errors


def check_release_gates(bundle_root: Path) -> Tuple[bool, List[str]]:
    """Check release-gate assets declared by the runtime contract."""
    errors = []
    contract = load_runtime_contract()
    gates = contract.get("release_gates")
    if not isinstance(gates, list) or not gates:
        errors.append("release_gates missing from runtime contract")
        return False, errors

    gate_ids = []
    for gate in gates:
        if not isinstance(gate, dict):
            errors.append("release_gate malformed: expected object")
            continue
        gate_id = str(gate.get("id") or "")
        if not gate_id:
            errors.append("release_gate missing id")
            continue
        gate_ids.append(gate_id)
        for field in ("script", "workspace", "launcher"):
            relative = str(gate.get(field) or "")
            if not relative:
                continue
            if not _contract_path(bundle_root, relative).exists():
                errors.append("release_gate.%s.%s missing: %s" % (gate_id, field, relative))
        if gate.get("allow_system_tool_fallback") is True:
            errors.append("release_gate.%s must not allow system tool fallback" % gate_id)

    required = [
        "runtime_contract",
        "cpp_smoke_workspace",
        "gui_headless_smoke",
        "win7_windowed_gui_smoke",
    ]
    for gate_id in required:
        if gate_id not in gate_ids:
            errors.append("release_gate.%s missing from runtime contract" % gate_id)

    return len(errors) == 0, errors


def check_launchers(bundle_root: Path) -> Tuple[bool, List[str]]:
    """Check launcher entry points exist."""
    errors = []
    launchers = [
        "EmbedAgent.exe",
        "embedagent-gui.exe",
        "embedagent.cmd",
        "embedagent-tui.cmd",
        "embedagent-gui.cmd",
    ]

    for launcher in launchers:
        if not (bundle_root / launcher).exists():
            errors.append(f"Missing launcher: {launcher}")

    return len(errors) == 0, errors


def check_config_files(bundle_root: Path) -> Tuple[bool, List[str]]:
    """Check config templates exist."""
    errors = []
    configs = [
        "config/config.json",
        "config/config.json.template",
        "config/permission-rules.json",
    ]

    for config in configs:
        if not (bundle_root / config).exists():
            errors.append(f"Missing config: {config}")

    return len(errors) == 0, errors


def check_documentation(bundle_root: Path) -> Tuple[bool, List[str]]:
    """Check documentation exists."""
    errors = []
    docs = [
        "docs/configuration-guide.md",
        "docs/win7-preflight-checklist.md",
        "docs/intranet-deployment.md",
    ]

    for doc in docs:
        if not (bundle_root / doc).exists():
            errors.append(f"Missing documentation: {doc}")

    return len(errors) == 0, errors


def check_static_files(bundle_root: Path) -> Tuple[bool, List[str]]:
    """Check GUI static files are included."""
    errors = []
    static_files = [
        "app/embedagent/frontend/gui/static/index.html",
        "app/embedagent/frontend/gui/static/assets",
    ]

    for file in static_files:
        if not (bundle_root / file).exists():
            errors.append(f"Missing static file: {file}")

    return len(errors) == 0, errors


def check_manifest(bundle_root: Path) -> Tuple[bool, List[str]]:
    """Check bundle manifest exists and is valid."""
    errors = []
    manifest_path = bundle_root / "manifests" / "bundle-manifest.json"

    if not manifest_path.exists():
        errors.append("Missing: manifests/bundle-manifest.json")
        return False, errors

    try:
        with open(manifest_path) as f:
            manifest = json.load(f)

        required_keys = ["schema_version", "components"]
        for key in required_keys:
            if key not in manifest:
                errors.append(f"Manifest missing key: {key}")
        if "bundle_id" not in manifest and "artifact_name" not in manifest:
            errors.append("Manifest missing identifier key: bundle_id or artifact_name")
    except json.JSONDecodeError as e:
        errors.append(f"Invalid manifest JSON: {e}")

    return len(errors) == 0, errors


def main():
    args = parse_args()
    contract = load_runtime_contract()
    if args.bundle_root:
        bundle_root = Path(args.bundle_root)
    else:
        bundle_root = get_bundle_root()
        if bundle_root is None:
            write_json_report(
                args.json_report,
                {
                    "ok": False,
                    "bundle_root": "",
                    "checks": [],
                    "runtime_contract": runtime_contract_summary(contract),
                    "error": "Cannot find bundle root. Please provide path as argument.",
                },
            )
            print("Error: Cannot find bundle root. Please provide path as argument.")
            return 1
    all_passed = True
    checks = [
        ("Python Runtime", check_python_runtime),
        ("Site Packages", check_site_packages),
        ("External Tools", check_external_tools),
        ("Release Gates", check_release_gates),
        ("Launchers", check_launchers),
        ("Config Files", check_config_files),
        ("Documentation", check_documentation),
        ("Static Files", check_static_files),
        ("Manifest", check_manifest),
    ]

    check_payloads = []
    for name, check_func in checks:
        passed, errors = check_func(bundle_root)
        check_payloads.append({"name": name, "ok": passed, "errors": errors})
        if not passed:
            all_passed = False

    write_json_report(
        args.json_report,
        {
            "ok": all_passed,
            "bundle_root": str(bundle_root),
            "checks": check_payloads,
            "runtime_contract": runtime_contract_summary(contract),
        },
    )

    print(f"Checking bundle: {bundle_root}")
    print("=" * 60)
    all_errors = []
    for item in check_payloads:
        status = "[PASS]" if item["ok"] else "[FAIL]"
        print(f"{status} {item['name']}")
        for error in item["errors"]:
            print(f"   - {error}")
            all_errors.append(error)

    print("=" * 60)
    if all_passed:
        print("All checks passed! Bundle is ready for offline deployment.")
        return 0
    else:
        print(f"Found {len(all_errors)} issue(s). Bundle may not work offline.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
