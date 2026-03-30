#!/usr/bin/env python3
"""
Export all Python dependencies for offline bundle.
Ensures zero external dependencies in the final package.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Set


def get_all_dependencies(project_root: str) -> List[str]:
    """Get full dependency tree using pip freeze."""
    # Install project in isolated env and get all deps
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"],
        capture_output=True,
        text=True,
        cwd=project_root
    )
    if result.returncode != 0:
        print(f"Error getting dependencies: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    
    deps = []
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            deps.append(line)
    return deps


def export_site_packages(
    project_root: str,
    output_dir: str,
    python_version: str = "3.8"
) -> None:
    """Export complete site-packages for offline use."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print("Step 1: Getting full dependency list...")
    deps = get_all_dependencies(project_root)
    print(f"Found {len(deps)} packages")
    
    # Create requirements file with pinned versions
    requirements_file = output_path / "requirements-pinned.txt"
    with open(requirements_file, "w") as f:
        f.write("# Auto-generated pinned requirements for offline bundle\n")
        f.write(f"# Python {python_version}\n\n")
        for dep in sorted(deps):
            f.write(f"{dep}\n")
    print(f"Written pinned requirements to {requirements_file}")
    
    # Export wheels for all dependencies
    wheels_dir = output_path / "wheels"
    wheels_dir.mkdir(exist_ok=True)
    
    print("\nStep 2: Downloading wheels for all dependencies...")
    result = subprocess.run(
        [
            sys.executable, "-m", "pip", "download",
            "-r", str(requirements_file),
            "-d", str(wheels_dir),
            "--only-binary", ":all:",
            "--platform", "win_amd64",
            "--python-version", python_version,
            "--no-deps"
        ],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Warning: Some packages may not have wheels: {result.stderr}")
    
    wheel_count = len(list(wheels_dir.glob("*.whl")))
    print(f"Downloaded {wheel_count} wheels to {wheels_dir}")
    
    # Create complete site-packages
    site_packages_dir = output_path / "site-packages"
    site_packages_dir.mkdir(exist_ok=True)
    
    print("\nStep 3: Installing wheels to site-packages...")
    for wheel in wheels_dir.glob("*.whl"):
        result = subprocess.run(
            [
                sys.executable, "-m", "pip", "install",
                str(wheel),
                "-t", str(site_packages_dir),
                "--no-deps",
                "--no-index"
            ],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"Warning: Failed to install {wheel.name}: {result.stderr}")
    
    # Install source distributions if any
    for sdist in wheels_dir.glob("*.tar.gz"):
        result = subprocess.run(
            [
                sys.executable, "-m", "pip", "install",
                str(sdist),
                "-t", str(site_packages_dir),
                "--no-deps",
                "--no-index"
            ],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"Warning: Failed to install {sdist.name}: {result.stderr}")
    
    # Count installed packages
    pkg_count = len([d for d in site_packages_dir.iterdir() if d.is_dir() and not d.name.endswith(".dist-info")])
    print(f"\nInstalled {pkg_count} packages to {site_packages_dir}")
    
    # Generate manifest
    manifest = {
        "python_version": python_version,
        "platform": "win_amd64",
        "total_packages": pkg_count,
        "packages": sorted([d.name for d in site_packages_dir.iterdir() if d.is_dir() and not d.name.endswith(".dist-info")]),
        "requirements": deps
    }
    
    manifest_file = output_path / "site-packages-manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Written manifest to {manifest_file}")


def verify_site_packages(site_packages_dir: str) -> bool:
    """Verify critical packages are present."""
    sp = Path(site_packages_dir)
    
    critical_packages = [
        # TUI
        "prompt_toolkit",
        "rich",
        # GUI
        "webview",
        "fastapi",
        "uvicorn",
        "websockets",
        # FastAPI deps
        "starlette",
        "pydantic",
        "anyio",
        # Common
        "click",
        "h11",
        "idna",
        "sniffio",
        "typing_extensions",
    ]
    
    missing = []
    for pkg in critical_packages:
        # Check for package directory (various naming conventions)
        found = False
        for variant in [pkg, pkg.replace("-", "_"), pkg.replace("_", "-")]:
            if (sp / variant).exists() or (sp / f"{variant}.py").exists():
                found = True
                break
            # Check for dist-info
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
        description="Export Python dependencies for offline bundle"
    )
    parser.add_argument(
        "--output-dir",
        default="build/offline-cache/site-packages-export",
        help="Output directory for exported dependencies"
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory"
    )
    parser.add_argument(
        "--python-version",
        default="3.8",
        help="Target Python version"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing site-packages"
    )
    
    args = parser.parse_args()
    
    if args.verify_only:
        site_packages = Path(args.output_dir) / "site-packages"
        if not site_packages.exists():
            print(f"Site-packages not found: {site_packages}")
            sys.exit(1)
        success = verify_site_packages(str(site_packages))
        sys.exit(0 if success else 1)
    
    # Export dependencies
    export_site_packages(
        args.project_root,
        args.output_dir,
        args.python_version
    )
    
    # Verify
    site_packages = Path(args.output_dir) / "site-packages"
    if site_packages.exists():
        verify_site_packages(str(site_packages))
    
    print(f"\n{'='*60}")
    print("Export complete!")
    print(f"Output: {args.output_dir}")
    print(f"Use this directory as -SitePackagesRoot in prepare-offline.ps1")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
