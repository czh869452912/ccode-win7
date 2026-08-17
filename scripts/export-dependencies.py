#!/usr/bin/env python3
"""
Export all Python dependencies for offline bundle.
Ensures zero external dependencies in the final package.

Uses uv (preferred) if available, falls back to pip.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from bundle_plan import load_bundle_plan as _load_compiled_bundle_plan
except ImportError:  # pragma: no cover - module loading by a test harness
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from bundle_plan import load_bundle_plan as _load_compiled_bundle_plan


def _run(cmd: List[str], cwd: str = None, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            "Command failed: {0}\n{1}".format(
                " ".join(cmd),
                result.stderr.strip(),
            )
        )
    return result


def write_json_report(path: str, payload: Dict) -> None:
    if not path:
        return
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


PYTHON_FEATURES = frozenset(("gui", "tui"))


def find_uv():
    """Return path to uv executable if available."""
    import shutil as sh

    return sh.which("uv")


def _validated_feature_ids(feature_ids: Tuple[str, ...]) -> Tuple[str, ...]:
    normalized = tuple(sorted(set(str(item or "").strip() for item in feature_ids)))
    if any(not item or item not in PYTHON_FEATURES for item in normalized):
        raise ValueError("unknown python feature")
    return normalized


def get_all_dependencies(project_root: str, feature_ids: Tuple[str, ...] = ()) -> List[str]:
    """Export only the locked third-party features selected by the bundle plan."""
    features = _validated_feature_ids(feature_ids)
    uv = find_uv()
    lock_file = Path(project_root) / "uv.lock"

    if uv and lock_file.exists():
        print("Using uv export from uv.lock...")
        command = [
            uv,
            "export",
            "--no-hashes",
            "--format",
            "requirements-txt",
            "--no-emit-workspace",
            "--no-dev",
        ]
        for feature_id in features:
            command.extend(("--extra", feature_id))
        result = _run(command, cwd=project_root)
        deps = []
        for line in result.stdout.splitlines():
            line = line.strip()
            # Skip comments, editable installs, annotation lines, blank lines
            if (
                not line
                or line.startswith("#")
                or line.startswith("-e")
                or line.startswith("    #")
            ):
                continue
            deps.append(line)
        return deps

    raise RuntimeError("uv and uv.lock are required for plan-selected dependency export")


def build_project_wheels(
    project_root: str,
    wheelhouse: Path,
    cache_dir: str = "",
    offline: bool = False,
    selected_distributions: Tuple[str, ...] = (),
    bundle_plan_path: str = "",
) -> List[Path]:
    """Build and validate exactly the plan-selected project distributions."""
    root = Path(project_root).resolve()
    build_script = root / "scripts" / "build-python-distributions.py"
    check_script = root / "scripts" / "check-python-distributions.py"
    command = [sys.executable, str(build_script), "--dist-dir", str(wheelhouse)]
    if cache_dir:
        command.extend(["--cache-dir", str(cache_dir)])
    if offline:
        command.append("--offline")
    if bundle_plan_path:
        command.extend(["--bundle-plan", str(bundle_plan_path)])
    _run(command, cwd=str(root))
    check_command = [sys.executable, str(check_script), "--dist-dir", str(wheelhouse)]
    if bundle_plan_path:
        check_command.extend(["--bundle-plan", str(bundle_plan_path)])
    _run(check_command, cwd=str(root))

    generated_gitignore = wheelhouse / ".gitignore"
    if generated_gitignore.is_file():
        if generated_gitignore.read_text(encoding="ascii").strip() != "*":
            raise RuntimeError("unexpected wheelhouse .gitignore contents")
        generated_gitignore.unlink()

    wheels = []
    for distribution in selected_distributions:
        filename_prefix = distribution.replace("-", "_") + "-"
        candidates = sorted(
            path
            for path in wheelhouse.glob(filename_prefix + "*.whl")
            if path.is_file() and not path.is_symlink()
        )
        if len(candidates) != 1:
            raise RuntimeError("Expected one wheel for {0}".format(distribution))
        wheels.append(candidates[0])
    return wheels


def install_project_wheels(
    project_root: str,
    site_packages_dir: Path,
    wheelhouse: Path,
    wheels: List[Path],
) -> None:
    """Install only validated local project wheels, with all network resolution disabled."""
    uv = find_uv()
    wheel_args = [str(path) for path in wheels]
    if uv:
        command = [
            uv,
            "pip",
            "install",
            "--target",
            str(site_packages_dir),
            "--no-index",
            "--find-links",
            str(wheelhouse),
            "--no-deps",
        ] + wheel_args
    else:
        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(site_packages_dir),
            "--no-index",
            "--find-links",
            str(wheelhouse),
            "--no-deps",
        ] + wheel_args
    _run(command, cwd=project_root)


_GENERATED_EXPORT_ENTRIES = frozenset(
    (
        "requirements-pinned.txt",
        "site-packages",
        "site-packages-manifest.json",
        "wheels",
    )
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_bundle_plan(path: str, expected_sha256: str = ""):
    if not path:
        raise ValueError("bundle plan is required")
    plan_path = Path(path)
    if not plan_path.is_file():
        raise ValueError("bundle plan not found")
    plan_sha256 = _sha256_file(plan_path)
    if expected_sha256 and plan_sha256 != str(expected_sha256).strip().lower():
        raise ValueError("bundle plan hash mismatch")
    payload, project_distributions = _load_compiled_bundle_plan(plan_path)
    feature_ids = _validated_feature_ids(tuple(payload.get("python_feature_ids") or ()))
    flavor_id = str(payload.get("flavor_id") or "").strip()
    if not flavor_id:
        raise ValueError("bundle plan flavor is required")
    return payload, plan_sha256, feature_ids, project_distributions


def clean_export_root(output_dir: Path) -> Path:
    root = Path(output_dir)
    if root.exists():
        if root.is_symlink() or not root.is_dir():
            raise ValueError("export root must be a normal directory")
        unknown = sorted(
            entry.name for entry in root.iterdir() if entry.name not in _GENERATED_EXPORT_ENTRIES
        )
        if unknown:
            raise ValueError("unexpected export entry: %s" % unknown[0])
        for name in sorted(_GENERATED_EXPORT_ENTRIES):
            entry = root / name
            if not entry.exists():
                continue
            if entry.is_symlink():
                raise ValueError("generated export entry must not be a reparse point: %s" % entry)
            if entry.is_dir():
                shutil.rmtree(str(entry))
            else:
                entry.unlink()
    else:
        root.mkdir(parents=True, exist_ok=True)
    return root


def export_site_packages(
    project_root: str,
    output_dir: str,
    python_version: str = "3.8",
    cache_dir: str = "",
    offline: bool = False,
    feature_ids: Tuple[str, ...] = (),
    flavor_id: str = "",
    bundle_plan_sha256: str = "",
    project_distributions: Tuple[str, ...] = (),
    bundle_plan_path: str = "",
) -> None:
    """Export complete site-packages for offline use."""
    if not project_distributions:
        raise ValueError("bundle plan project distributions are required")
    unknown_distributions = set(project_distributions) - {
        "embedagent-core",
        "embedagent-protocol",
        "embedagent-host",
        "embedagent-composition",
        "embedagent-workflow-cpp",
        "embedagent-shell",
    }
    if unknown_distributions:
        raise ValueError("unknown bundle plan distribution: %s" % sorted(unknown_distributions)[0])
    if cache_dir:
        os.environ["UV_CACHE_DIR"] = str(Path(cache_dir).resolve())
    if offline:
        os.environ["UV_OFFLINE"] = "1"
    output_path = clean_export_root(Path(output_dir))

    print("Step 1: Getting full dependency list...")
    features = _validated_feature_ids(feature_ids)
    deps = get_all_dependencies(project_root, features)
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

    wheelhouse = output_path / "wheels"
    print("\nStep 2: Building checked project wheels...")
    project_wheels = build_project_wheels(
        project_root,
        wheelhouse,
        cache_dir=cache_dir,
        offline=offline,
        selected_distributions=project_distributions,
        bundle_plan_path=bundle_plan_path,
    )

    print("\nStep 3: Installing third-party dependencies into site-packages...")
    uv = find_uv()
    if uv:
        # uv pip install --target is fast and handles platform constraints well
        command = [
            uv,
            "pip",
            "install",
        ]
        if offline:
            command.append("--offline")
        command.extend(
            [
                "--target",
                str(site_packages_dir),
                "--requirement",
                str(requirements_file),
                "--python",
                python_version,
            ]
        )
        result = _run(
            command,
            cwd=project_root,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError("uv dependency export failed: {0}".format(result.stderr.strip()))
    else:
        # pip fallback
        result = _run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--target",
                str(site_packages_dir),
                "--requirement",
                str(requirements_file),
                "--no-deps",
            ],
            cwd=project_root,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError("pip dependency export failed: {0}".format(result.stderr.strip()))

    print("\nStep 4: Installing checked project wheels without network access...")
    install_project_wheels(project_root, site_packages_dir, wheelhouse, project_wheels)

    # Remove transient installer metadata that embeds local cache paths.
    for metadata_name in ("direct_url.json", "uv_cache.json"):
        for metadata_path in site_packages_dir.rglob(metadata_name):
            metadata_path.unlink()
    for record_path in site_packages_dir.rglob("RECORD"):
        records = [
            line
            for line in record_path.read_text(encoding="utf-8").splitlines()
            if not line.startswith(
                (
                    record_path.parent.name + "/direct_url.json,",
                    record_path.parent.name + "/uv_cache.json,",
                )
            )
        ]
        record_path.write_text("\n".join(records) + "\n", encoding="utf-8")
    # Remove editable .pth files that would point back to dev tree
    for pth in site_packages_dir.glob("__editable__*.pth"):
        pth.unlink()
        print(f"Removed editable link: {pth.name}")

    # Count installed packages
    pkg_count = len(
        [d for d in site_packages_dir.iterdir() if d.is_dir() and not d.name.endswith(".dist-info")]
    )
    print(f"\nInstalled {pkg_count} packages to {site_packages_dir}")

    # Generate manifest
    manifest = {
        "python_version": python_version,
        "platform": "win_amd64",
        "total_packages": pkg_count,
        "packages": sorted(
            [
                d.name
                for d in site_packages_dir.iterdir()
                if d.is_dir() and not d.name.endswith(".dist-info")
            ]
        ),
        "requirements": deps,
        "flavor_id": flavor_id,
        "bundle_plan_sha256": bundle_plan_sha256,
        "python_feature_ids": list(features),
        "project_distributions": list(project_distributions),
        "project_wheels": [path.name for path in project_wheels],
        "wheel_hashes": {path.name: _sha256_file(path) for path in project_wheels},
    }
    manifest_file = output_path / "site-packages-manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Written manifest to {manifest_file}")


def verify_site_packages(
    site_packages_dir: str,
    feature_ids: Tuple[str, ...] = (),
    project_distributions: Tuple[str, ...] = (),
) -> Tuple[bool, List[str]]:
    """Verify critical packages are present."""
    sp = Path(site_packages_dir)
    package_names = {
        "embedagent-core": "embedagent_core",
        "embedagent-protocol": "embedagent_protocol",
        "embedagent-host": "embedagent_host",
        "embedagent-composition": "embedagent_composition",
        "embedagent-workflow-cpp": "embedagent_workflow_cpp",
        "embedagent-shell": "embedagent",
    }
    critical_packages = [package_names[item] for item in project_distributions]
    features = _validated_feature_ids(feature_ids)
    if "tui" in features:
        critical_packages.extend(("prompt_toolkit", "rich"))
    if "gui" in features:
        critical_packages.extend(
            (
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
            )
        )

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
        return False, missing
    print(f"\nAll {len(critical_packages)} critical packages verified!")
    return True, missing


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
    parser.add_argument(
        "--json-report",
        default="",
        help="Optional path for a machine-readable JSON report",
    )
    parser.add_argument(
        "--cache-dir",
        default="",
        help="Optional isolated uv cache directory for project wheel builds",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Disable network access during project wheel builds",
    )
    parser.add_argument(
        "--bundle-plan",
        default="",
        help="Compiled bundle plan selecting Python dependency features",
    )
    parser.add_argument(
        "--bundle-plan-sha256",
        default="",
        help="Expected SHA-256 of the compiled bundle plan",
    )

    args = parser.parse_args()

    try:
        plan, plan_sha256, feature_ids, project_distributions = load_bundle_plan(
            args.bundle_plan,
            args.bundle_plan_sha256,
        )
        flavor_id = str(plan["flavor_id"])
        if args.verify_only:
            site_packages = Path(args.output_dir) / "site-packages"
            if not site_packages.exists():
                payload = {
                    "ok": False,
                    "missing_packages": ["site-packages"],
                    "mode": "verify-only",
                }
                write_json_report(args.json_report, payload)
                print(f"Site-packages not found: {site_packages}")
                sys.exit(1)
            success, missing = verify_site_packages(
                str(site_packages), feature_ids, project_distributions
            )
            write_json_report(
                args.json_report,
                {
                    "ok": success,
                    "mode": "verify-only",
                    "site_packages_root": str(site_packages),
                    "missing_packages": missing,
                    "flavor_id": flavor_id,
                    "bundle_plan_sha256": plan_sha256,
                    "python_feature_ids": list(feature_ids),
                },
            )
            sys.exit(0 if success else 1)

        export_site_packages(
            args.project_root,
            args.output_dir,
            args.python_version,
            cache_dir=args.cache_dir,
            offline=args.offline,
            feature_ids=feature_ids,
            flavor_id=flavor_id,
            bundle_plan_sha256=plan_sha256,
            project_distributions=project_distributions,
            bundle_plan_path=args.bundle_plan,
        )

        site_packages = Path(args.output_dir) / "site-packages"
        if site_packages.exists():
            success, missing = verify_site_packages(
                str(site_packages), feature_ids, project_distributions
            )
            manifest = json.loads(
                (Path(args.output_dir) / "site-packages-manifest.json").read_text(encoding="utf-8")
            )
            write_json_report(
                args.json_report,
                {
                    "ok": success,
                    "mode": "export",
                    "output_dir": args.output_dir,
                    "site_packages_root": str(site_packages),
                    "requirements_file": str(Path(args.output_dir) / "requirements-pinned.txt"),
                    "wheelhouse": str(Path(args.output_dir) / "wheels"),
                    "flavor_id": flavor_id,
                    "bundle_plan_sha256": plan_sha256,
                    "python_feature_ids": list(feature_ids),
                    "project_distributions": list(project_distributions),
                    "project_wheels": manifest.get("project_wheels", []),
                    "wheel_hashes": manifest.get("wheel_hashes", {}),
                    "missing_packages": missing,
                },
            )

        print(f"\n{'=' * 60}")
        print("Export complete!")
        print(f"Output: {args.output_dir}")
        print("Use this directory as -SitePackagesRoot in prepare-offline.ps1")
        print(f"{'=' * 60}")
    except Exception as exc:
        write_json_report(
            args.json_report,
            {
                "ok": False,
                "mode": "export",
                "output_dir": args.output_dir,
                "error": str(exc),
            },
        )
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
