#!/usr/bin/env python3
"""
Offline Bundle Dependency Checker
Ensures all dependencies are present for zero-dependency deployment.
"""
from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "app"):
    if candidate.exists():
        sys.path.insert(0, str(candidate))

from embedagent.runtime_discovery import discover_bundle_root


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
    
    # Critical packages that must be present
    critical = {
        # Core
        "embedagent": ["embedagent"],
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


def check_external_tools(bundle_root: Path) -> Tuple[bool, List[str]]:
    """Check external binary tools."""
    errors = []
    tools = {
        "git": ["bin", "git", "cmd", "git.exe"],
        "rg": ["bin", "rg", "rg.exe"],
        "ctags": ["bin", "ctags", "ctags.exe"],
        "clang": ["bin", "llvm", "bin", "clang.exe"],
        "clang-tidy": ["bin", "llvm", "bin", "clang-tidy.exe"],
    }
    
    for name, path_parts in tools.items():
        tool_path = bundle_root.joinpath(*path_parts)
        if not tool_path.exists():
            errors.append(f"Missing tool: {name} ({tool_path})")
    
    return len(errors) == 0, errors


def check_launchers(bundle_root: Path) -> Tuple[bool, List[str]]:
    """Check launcher scripts exist."""
    errors = []
    launchers = [
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
