#!/usr/bin/env python3
"""
Export all Python dependencies for offline bundle.
Ensures zero external dependencies in the final package.

Uses uv (preferred) if available, falls back to pip.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List


def _run(cmd: List[str], cwd: str = None, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if check and result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result


def find_uv() -> str | None:
    """Return path to uv executable if available."""
    import shutil as sh
    return sh.which("uv")


def get_all_dependencies(project_root: str) -> List[str]:
    """Get full pinned dependency list from uv.lock or pip freeze."""
    uv = find_uv()
    lock_file = Path(project_root) / "uv.lock"

    if uv and lock_file.exists():
        print("Using uv export from uv.lock...")
        result = _run(
            [uv, "export", "--no-hashes", "--format", "requirements-txt"],
            cwd=project_root,
        )
        deps = []
        for line in result.stdout.splitlines():
            line = line.strip()
            # Skip comments, editable installs, annotation lines, blank lines
            if not line or line.startswith("#") or line.startswith("-e") or line.startswith("    #"):
                continue
            deps.append(line)
        return deps

    # Fallback: pip freeze
    print("uv not found or no uv.lock, falling back to pip freeze...")
    result = _run([sys.executable, "-m", "pip", "freeze", "--all"], cwd=project_root)
    deps = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            deps.append(line)
    return deps


def export_site_packages(
    project_root: str,
    output_dir: str,
    python_version: str = "3.8",
) -> None:
    """Export complete site-packages for offline use."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("Step 1: Getting full dependency list...")
    deps = get_all_dependencies(project_root)
    print(f"Found {len(deps)} packages")

    # Write pinned requirements
    requirements_file = output_path / "requirements-pinned.txt"
    with open(requirements_file, "w") as f:
        f.write("# Auto-generated pinned requirements for offline bundle\n")
        f.write(f"# Python {python_version}\n\n")
        for dep in sorted(deps):
            f.write(f"{dep}\n")
    print(f"Written pinned requirements to {requirements_file}")

    # Create site-packages dir
    site_packages_dir = output_path / "site-packages"
    if site_packages_dir.exists():
        shutil.rmtree(site_packages_dir)
    site_packages_dir.mkdir()

    print("\nStep 2: Installing dependencies into site-packages...")
    uv = find_uv()
    if uv:
        # uv pip install --target is fast and handles platform constraints well
        result = _run(
            [
                uv, "pip", "install",
                "--target", str(site_packages_dir),
                "--requirement", str(requirements_file),
                "--python", python_version,
            ],
            cwd=project_root,
            check=False,
        )
        if result.returncode != 0:
            print(f"Warning: uv pip install reported issues:\n{result.stderr}")
    else:
        # pip fallback
        result = _run(
            [
                sys.executable, "-m", "pip", "install",
                "--target", str(site_packages_dir),
                "--requirement", str(requirements_file),
                "--no-deps",
            ],
            cwd=project_root,
            check=False,
        )
        if result.returncode != 0:
            print(f"Warning: pip install reported issues:\n{result.stderr}")

    # Install the project itself (no-deps, to get embedagent package code)
    print("\nStep 3: Installing project package (no-deps)...")
    if uv:
        result = _run(
            [uv, "pip", "install", "--target", str(site_packages_dir), ".", "--no-deps"],
            cwd=project_root,
            check=False,
        )
    else:
        result = _run(
            [sys.executable, "-m", "pip", "install", "--target", str(site_packages_dir), ".", "--no-deps"],
            cwd=project_root,
            check=False,
        )

    # Remove editable .pth files that would point back to dev tree
    for pth in site_packages_dir.glob("__editable__*.pth"):
        pth.unlink()
        print(f"Removed editable link: {pth.name}")

    # Count installed packages
    pkg_count = len([
        d for d in site_packages_dir.iterdir()
        if d.is_dir() and not d.name.endswith(".dist-info")
    ])
    print(f"\nInstalled {pkg_count} packages to {site_packages_dir}")

    # Generate manifest
    manifest = {
        "python_version": python_version,
        "platform": "win_amd64",
        "total_packages": pkg_count,
        "packages": sorted([
            d.name for d in site_packages_dir.iterdir()
            if d.is_dir() and not d.name.endswith(".dist-info")
        ]),
        "requirements": deps,
    }
    manifest_file = output_path / "site-packages-manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Written manifest to {manifest_file}")


def verify_site_packages(site_packages_dir: str) -> bool:
    """Verify critical packages are present."""
    sp = Path(site_packages_dir)

    critical_packages = [
        "prompt_toolkit",
        "rich",
        "webview",
        "fastapi",
        "uvicorn",
        "websockets",
        "starlette",
        "pydantic",
        "anyio",
        "click",
        "h11",
        "idna",
        "sniffio",
        "typing_extensions",
    ]

    missing = []
    for pkg in critical_packages:
        found = False
        for variant in [pkg, pkg.replace("-", "_"), pkg.replace("_", "-")]:
            if (sp / variant).exists() or (sp / f"{variant}.py").exists():
                found = True
                break
            if list(sp.glob(f"{variant}-*.dist-info")):
                found = True
                break
        if not found:
            missing.append(pkg)

    if missing:
        print(f"\nMissing critical packages: {', '.join(missing)}")
        return False

    print(f"\nAll {len(critical_packages)} critical packages verified!")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Export Python dependencies for offline bundle (uv-aware)"
    )
    parser.add_argument(
        "--output-dir",
        default="build/offline-cache/site-packages-export",
        help="Output directory for exported dependencies",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory",
    )
    parser.add_argument(
        "--python-version",
        default="3.8",
        help="Target Python version",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing site-packages",
    )

    args = parser.parse_args()

    if args.verify_only:
        site_packages = Path(args.output_dir) / "site-packages"
        if not site_packages.exists():
            print(f"Site-packages not found: {site_packages}")
            sys.exit(1)
        success = verify_site_packages(str(site_packages))
        sys.exit(0 if success else 1)

    export_site_packages(
        args.project_root,
        args.output_dir,
        args.python_version,
    )

    site_packages = Path(args.output_dir) / "site-packages"
    if site_packages.exists():
        verify_site_packages(str(site_packages))

    print(f"\n{'='*60}")
    print("Export complete!")
    print(f"Output: {args.output_dir}")
    print("Use this directory as -SitePackagesRoot in prepare-offline.ps1")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
