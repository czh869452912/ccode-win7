#!/usr/bin/env python3
"""
Offline Bundle Dependency Checker
Ensures all dependencies are present for zero-dependency deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "scripts" / "offline-runtime-contract.json"
PYTHON_FEATURE_PACKAGES = {
    "tui": {
        "prompt_toolkit": ("prompt_toolkit", "prompt-toolkit"),
        "rich": ("rich",),
        "pygments": ("pygments", "Pygments"),
        "wcwidth": ("wcwidth",),
    },
    "gui": {
        "webview": ("webview", "pywebview"),
        "fastapi": ("fastapi",),
        "uvicorn": ("uvicorn",),
        "websockets": ("websockets",),
        "starlette": ("starlette",),
        "pydantic": ("pydantic", "pydantic_core"),
        "anyio": ("anyio",),
        "sniffio": ("sniffio",),
        "h11": ("h11",),
        "idna": ("idna",),
        "click": ("click",),
        "typing_extensions": ("typing_extensions", "typing-extensions"),
        "colorama": ("colorama",),
    },
}
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
    parser.add_argument(
        "--bundle-plan",
        default="",
        help="Optional source plan path that must match the plan embedded in the bundle",
    )
    parser.add_argument(
        "--bundle-plan-sha256",
        default="",
        help="Expected SHA-256 for both the source and embedded bundle plan",
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
    if payload.get("schema_version") != 2:
        raise ValueError("runtime contract must use schema version 2")
    if not isinstance(payload.get("runtime_components"), list):
        raise ValueError("runtime contract missing runtime_components array")
    return payload


def managed_runtime_tools(contract: Dict, component_ids=None) -> List[Dict]:
    tools = []
    selected = set(component_ids) if component_ids is not None else None
    for component in contract.get("runtime_components") or []:
        if not isinstance(component, dict):
            continue
        if selected is not None and str(component.get("id") or "") not in selected:
            continue
        for tool in component.get("managed_tools") or []:
            if isinstance(tool, dict):
                tools.append(tool)
    return tools


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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json_object(path: Path, label: str) -> Dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"{label} could not be read: {exc}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is invalid JSON: {exc}")
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def load_bundle_plan(
    bundle_root: Path,
    source_plan_path: str = "",
    expected_sha256: str = "",
) -> Tuple[Optional[Dict], Optional[Dict], Dict, List[str]]:
    errors = []
    manifest_path = bundle_root / "manifests" / "bundle-manifest.json"
    embedded_plan_path = bundle_root / "manifests" / "bundle-plan.json"
    details = {
        "path": str(embedded_plan_path),
        "source_path": str(source_plan_path or ""),
        "sha256": "",
    }
    try:
        manifest = _read_json_object(manifest_path, "bundle manifest")
    except ValueError as exc:
        return None, None, details, [str(exc)]
    try:
        plan = _read_json_object(embedded_plan_path, "embedded bundle plan")
    except ValueError as exc:
        return None, manifest, details, [str(exc)]

    actual_hash = _sha256(embedded_plan_path)
    details["sha256"] = actual_hash
    manifest_hash = str(manifest.get("bundle_plan_sha256") or "").lower()
    if actual_hash != manifest_hash:
        errors.append("Bundle plan hash mismatch against bundle manifest")
    if expected_sha256 and actual_hash != expected_sha256.lower():
        errors.append("Bundle plan hash mismatch against expected SHA-256")
    if source_plan_path:
        source_path = Path(source_plan_path)
        if not source_path.is_file():
            errors.append(f"Source bundle plan not found: {source_path}")
        else:
            source_hash = _sha256(source_path)
            if source_hash != actual_hash:
                errors.append("Embedded bundle plan hash mismatch against source plan")
    if plan.get("schema_version") != 1:
        errors.append("Unsupported bundle plan schema version")
    agent_manifest_path = bundle_root / "manifests" / "agent.json"
    agent_lock_path = bundle_root / "manifests" / "agent.lock.json"
    if not agent_manifest_path.is_file():
        errors.append("Embedded Agent manifest missing: manifests/agent.json")
    if not agent_lock_path.is_file():
        errors.append("Embedded Agent lock missing: manifests/agent.lock.json")
    elif _sha256(agent_lock_path) != str(plan.get("agent_lock_sha256") or "").lower():
        errors.append("Embedded Agent lock hash mismatch against bundle plan")
    return plan, manifest, details, errors


def _manifest_binding_errors(plan: Dict, manifest: Dict) -> List[str]:
    errors = []
    scalar_fields = ("flavor_id", "agent_lock_sha256")
    array_bindings = {
        "allowed_agent_application_ids": "allowed_agent_application_ids",
        "shell_ids": "shell_ids",
        "runtime_component_ids": "runtime_component_ids",
        "resolved_asset_ids": "asset_ids",
        "python_feature_ids": "python_feature_ids",
        "staged_launcher_ids": "launcher_ids",
        "gate_ids": "gate_ids",
    }
    for field in scalar_fields:
        if manifest.get(field) != plan.get(field):
            errors.append(f"Bundle manifest {field} does not match bundle plan")
    for manifest_field, plan_field in array_bindings.items():
        if manifest.get(manifest_field) != plan.get(plan_field):
            errors.append(f"Bundle manifest {manifest_field} does not match bundle plan")
    return errors


def _tool_known_paths(tool: Dict) -> List[str]:
    paths = list(tool.get("paths") or [])
    for alternative in tool.get("alternatives") or []:
        if isinstance(alternative, dict):
            paths.extend(alternative.get("paths") or [])
    for child in tool.get("children") or []:
        if isinstance(child, dict) and child.get("path"):
            paths.append(str(child["path"]))
    return paths


def _component_known_paths(component: Dict) -> List[str]:
    paths = list(component.get("paths") or [])
    for tool in component.get("managed_tools") or []:
        if isinstance(tool, dict):
            paths.extend(_tool_known_paths(tool))
    return paths


def _selected_runtime_errors(bundle_root: Path, component: Dict) -> List[str]:
    errors = []
    component_id = str(component.get("id") or "")
    if not _paths_exist(bundle_root, list(component.get("paths") or [])):
        errors.append(f"Selected runtime component missing required paths: {component_id}")
    for tool in component.get("managed_tools") or []:
        if not isinstance(tool, dict):
            continue
        tool_id = str(tool.get("id") or "")
        alternatives = tool.get("alternatives")
        if isinstance(alternatives, list):
            if not _alternative_exists(bundle_root, alternatives):
                errors.append(f"Selected runtime tool missing alternatives: {tool_id}")
        elif not _paths_exist(bundle_root, list(tool.get("paths") or [])):
            errors.append(f"Selected runtime tool missing required paths: {tool_id}")
        for child in tool.get("children") or []:
            if isinstance(child, dict) and child.get("path"):
                child_path = str(child["path"])
                if not _contract_path(bundle_root, child_path).exists():
                    errors.append(f"Selected runtime tool child missing: {child_path}")
    return errors


def _package_exists(site_packages: Path, variants) -> bool:
    for variant in variants:
        if (site_packages / variant).exists() or (site_packages / f"{variant}.py").exists():
            return True
        if list(site_packages.glob(f"{variant}-*.dist-info")):
            return True
        if list(site_packages.glob(f"{variant}_*.pyd")) or list(
            site_packages.glob(f"{variant}*.so")
        ):
            return True
    return False


def _selected_feature_errors(bundle_root: Path, feature_ids) -> List[str]:
    errors = []
    site_packages = bundle_root / "runtime" / "site-packages"
    for feature_id in feature_ids:
        packages = PYTHON_FEATURE_PACKAGES.get(str(feature_id))
        if packages is None:
            errors.append(f"Unknown selected Python feature: {feature_id}")
            continue
        for display_name, variants in packages.items():
            if not _package_exists(site_packages, variants):
                errors.append(f"Selected Python feature package missing: {display_name}")
    return errors


def validate_against_plan(
    bundle_root: Path,
    source_plan_path: str = "",
    expected_sha256: str = "",
) -> Tuple[bool, List[str]]:
    bundle_root = Path(bundle_root)
    plan, manifest, _details, errors = load_bundle_plan(
        bundle_root,
        source_plan_path=source_plan_path,
        expected_sha256=expected_sha256,
    )
    if plan is None or manifest is None:
        return False, errors
    errors.extend(_manifest_binding_errors(plan, manifest))

    contract = load_runtime_contract()
    components = {
        str(item.get("id") or ""): item
        for item in contract.get("runtime_components") or []
        if isinstance(item, dict)
    }
    launchers = {
        str(item.get("id") or ""): item
        for item in contract.get("launchers") or []
        if isinstance(item, dict)
    }
    gates = {
        str(item.get("id") or ""): item
        for item in contract.get("release_gates") or []
        if isinstance(item, dict)
    }
    selected_component_ids = set(plan.get("runtime_component_ids") or [])
    selected_launcher_ids = set(plan.get("launcher_ids") or [])
    selected_gate_ids = set(plan.get("gate_ids") or [])
    for label, selected, known in (
        ("runtime component", selected_component_ids, set(components)),
        ("launcher", selected_launcher_ids, set(launchers)),
        ("gate", selected_gate_ids, set(gates)),
        ("Python feature", set(plan.get("python_feature_ids") or []), set(PYTHON_FEATURE_PACKAGES)),
    ):
        for unknown_id in sorted(selected - known):
            errors.append(f"Unknown selected {label}: {unknown_id}")
    for unknown_shell in sorted(set(plan.get("shell_ids") or []) - {"cli", "tui", "gui"}):
        errors.append(f"Unknown selected shell: {unknown_shell}")

    planned_paths = set()
    known_paths = set()
    for component_id, component in components.items():
        component_paths = set(_component_known_paths(component))
        known_paths.update(component_paths)
        if component_id in selected_component_ids:
            planned_paths.update(component_paths)
            errors.extend(_selected_runtime_errors(bundle_root, component))
    for launcher_id, launcher in launchers.items():
        launcher_path = str(launcher.get("path") or "")
        if not launcher_path:
            continue
        known_paths.add(launcher_path)
        if launcher_id in selected_launcher_ids:
            planned_paths.add(launcher_path)
            if not _contract_path(bundle_root, launcher_path).exists():
                errors.append(f"Selected launcher missing: {launcher_id} ({launcher_path})")
    for gate_id, gate in gates.items():
        gate_paths = {
            str(gate.get(field) or "")
            for field in ("script", "workspace", "launcher")
            if gate.get(field)
        }
        known_paths.update(gate_paths)
        if gate_id in selected_gate_ids:
            planned_paths.update(gate_paths)
            for gate_path in gate_paths:
                if not _contract_path(bundle_root, gate_path).exists():
                    errors.append(f"Selected release gate path missing: {gate_id} ({gate_path})")

    gui_paths = {
        "app/embedagent/frontend/gui/static/index.html",
        "app/embedagent/frontend/gui/static/assets",
    }
    known_paths.update(gui_paths)
    if "gui" in set(plan.get("shell_ids") or []):
        planned_paths.update(gui_paths)
        for gui_path in gui_paths:
            if not _contract_path(bundle_root, gui_path).exists():
                errors.append(f"Selected GUI static path missing: {gui_path}")

    for relative_path in sorted(known_paths - planned_paths):
        if _contract_path(bundle_root, relative_path).exists():
            errors.append(f"Unplanned runtime content present: {relative_path}")
    errors.extend(_selected_feature_errors(bundle_root, plan.get("python_feature_ids") or []))
    return not errors, errors


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


def check_site_packages(bundle_root: Path, plan: Optional[Dict] = None) -> Tuple[bool, List[str]]:
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
    wheel_only_manifest = False
    manifest_payload = {}
    manifest_path = bundle_root / "manifests" / "bundle-manifest.json"
    if manifest_path.is_file():
        try:
            with open(manifest_path) as manifest_file:
                manifest_payload = json.load(manifest_file)
                wheel_only_manifest = manifest_payload.get("source_mode") == "wheel-installed"
        except (OSError, json.JSONDecodeError):
            wheel_only_manifest = False
    distribution_ids = tuple(
        (plan or {}).get("project_distribution_ids")
        or manifest_payload.get("project_distributions")
        or ()
    )
    if not distribution_ids:
        errors.append("Bundle manifest or bundle plan must declare project distributions")
    distribution_packages = {
        "embedagent-shell": "embedagent",
        "embedagent-core": "embedagent_core",
        "embedagent-protocol": "embedagent_protocol",
        "embedagent-host": "embedagent_host",
        "embedagent-composition": "embedagent_composition",
        "embedagent-workflow-cpp": "embedagent_workflow_cpp",
    }
    project_packages = tuple(
        (
            distribution_id,
            distribution_packages.get(distribution_id, distribution_id.replace("-", "_")),
        )
        for distribution_id in distribution_ids
    )
    for display_name, import_name in project_packages:
        if display_name == "embedagent-shell" and wheel_only_manifest:
            # Product code is intentionally staged under app/embedagent. Its
            # wheel metadata is represented by bundle-manifest project_wheels;
            # it must not be duplicated in runtime/site-packages.
            continue
        if display_name != "embedagent-shell" and not (sp / import_name).is_dir():
            errors.append("Missing project import package: %s" % display_name)
        dist_info_glob = "%s-*.dist-info" % display_name.replace("-", "_")
        if not any((candidate / "METADATA").is_file() for candidate in sp.glob(dist_info_glob)):
            errors.append("Missing project distribution metadata: %s" % display_name)

    feature_ids = (
        tuple(PYTHON_FEATURE_PACKAGES)
        if plan is None
        else tuple(plan.get("python_feature_ids") or [])
    )
    critical = {}
    for feature_id in feature_ids:
        critical.update(PYTHON_FEATURE_PACKAGES.get(str(feature_id), {}))

    for display_name, variants in critical.items():
        if not _package_exists(sp, variants):
            errors.append(f"Missing package: {display_name}")

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


def check_external_tools(
    bundle_root: Path, plan: Optional[Dict] = None, contract: Optional[Dict] = None
) -> Tuple[bool, List[str]]:
    """Check external binary tools."""
    errors = []
    contract = contract or load_runtime_contract()
    component_ids = None if plan is None else plan.get("runtime_component_ids") or []

    for tool in managed_runtime_tools(contract, component_ids):
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


def check_release_gates(
    bundle_root: Path, plan: Optional[Dict] = None, contract: Optional[Dict] = None
) -> Tuple[bool, List[str]]:
    """Check release-gate assets declared by the runtime contract."""
    errors = []
    contract = contract or load_runtime_contract()
    gates = contract.get("release_gates")
    if not isinstance(gates, list) or not gates:
        errors.append("release_gates missing from runtime contract")
        return False, errors

    selected_gate_ids = None if plan is None else set(plan.get("gate_ids") or [])
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
        if selected_gate_ids is not None and gate_id not in selected_gate_ids:
            continue
        for field in ("script", "workspace", "launcher"):
            relative = str(gate.get(field) or "")
            if not relative:
                continue
            if not _contract_path(bundle_root, relative).exists():
                errors.append("release_gate.%s.%s missing: %s" % (gate_id, field, relative))
        if gate.get("allow_system_tool_fallback") is True:
            errors.append("release_gate.%s must not allow system tool fallback" % gate_id)

    required = (
        list(selected_gate_ids)
        if selected_gate_ids is not None
        else [
            "runtime_contract",
            "win7_cli_smoke",
            "cpp_smoke_workspace",
            "gui_headless_smoke",
            "win7_windowed_gui_smoke",
        ]
    )
    for gate_id in required:
        if gate_id not in gate_ids:
            errors.append("release_gate.%s missing from runtime contract" % gate_id)

    return len(errors) == 0, errors


def check_launchers(
    bundle_root: Path, plan: Optional[Dict] = None, contract: Optional[Dict] = None
) -> Tuple[bool, List[str]]:
    """Check launcher entry points exist."""
    errors = []
    if plan is None:
        launchers = [
            "EmbedAgent.exe",
            "embedagent-gui.exe",
            "embedagent.cmd",
            "embedagent-tui.cmd",
            "embedagent-gui.cmd",
        ]
    else:
        contract = contract or load_runtime_contract()
        launcher_ids = set(plan.get("launcher_ids") or [])
        launchers = [
            str(item.get("path") or "")
            for item in contract.get("launchers") or []
            if isinstance(item, dict) and str(item.get("id") or "") in launcher_ids
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


def check_static_files(bundle_root: Path, plan: Optional[Dict] = None) -> Tuple[bool, List[str]]:
    """Check GUI static files are included."""
    errors = []
    if plan is not None and "gui" not in set(plan.get("shell_ids") or []):
        return True, errors
    static_files = [
        "app/embedagent/frontend/gui/static/index.html",
        "app/embedagent/frontend/gui/static/assets",
    ]

    for file in static_files:
        if not (bundle_root / file).exists():
            errors.append(f"Missing static file: {file}")

    return len(errors) == 0, errors


def check_manifest(bundle_root: Path, plan: Optional[Dict] = None) -> Tuple[bool, List[str]]:
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
        if "source_mode" in manifest:
            if manifest.get("source_mode") != "wheel-installed":
                errors.append("Manifest source_mode must be wheel-installed")
            expected_distributions = tuple(
                (plan or {}).get("project_distribution_ids")
                or manifest.get("project_distributions")
                or ()
            )
            actual_wheels = tuple(manifest.get("project_wheels") or ())
            actual_stems = tuple(
                (
                    "embedagent-shell"
                    if str(item).split("-", 1)[0].replace("_", "-") == "embedagent"
                    else str(item).split("-", 1)[0].replace("_", "-")
                )
                for item in actual_wheels
            )
            if actual_stems != expected_distributions:
                errors.append("Manifest project_wheels must match planned project distributions")
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
                    "bundle_plan": {
                        "path": "",
                        "source_path": args.bundle_plan,
                        "sha256": "",
                    },
                    "error": "Cannot find bundle root. Please provide path as argument.",
                },
            )
            print("Error: Cannot find bundle root. Please provide path as argument.")
            return 1
    plan, _manifest, plan_details, plan_errors = load_bundle_plan(
        bundle_root,
        source_plan_path=args.bundle_plan,
        expected_sha256=args.bundle_plan_sha256,
    )
    all_passed = True
    checks = [
        ("Python Runtime", check_python_runtime),
        ("Site Packages", lambda root: check_site_packages(root, plan)),
        ("External Tools", lambda root: check_external_tools(root, plan, contract)),
        ("Release Gates", lambda root: check_release_gates(root, plan, contract)),
        ("Launchers", lambda root: check_launchers(root, plan, contract)),
        ("Config Files", check_config_files),
        ("Documentation", check_documentation),
        ("Static Files", lambda root: check_static_files(root, plan)),
        ("Manifest", lambda root: check_manifest(root, plan)),
        (
            "Bundle Plan",
            lambda _root: (
                validate_against_plan(
                    bundle_root,
                    source_plan_path=args.bundle_plan,
                    expected_sha256=args.bundle_plan_sha256,
                )
                if not plan_errors
                else (False, plan_errors)
            ),
        ),
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
            "bundle_plan": plan_details,
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
