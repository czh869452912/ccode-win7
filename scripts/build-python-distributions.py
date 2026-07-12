#!/usr/bin/env python3
"""Create a clean wheelhouse for every Python distribution in the workspace."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

WORKSPACE_MEMBERS = (
    "packages/embedagent-core",
    "packages/embedagent-protocol",
    "packages/embedagent-host",
    "packages/embedagent-composition",
)


def _contains(parent, child):
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _remove_generated_path(path):
    if not path.exists():
        return
    if path.is_symlink():
        raise ValueError("refusing to remove a generated path through a symbolic link")
    if path.is_dir():
        shutil.rmtree(str(path))
    else:
        path.unlink()


def clean_generated_artifacts(project_root, dist_dir, package_roots):
    project_root = Path(project_root).resolve()
    dist_dir = Path(dist_dir).resolve()
    if dist_dir == project_root:
        raise ValueError("distribution directory must not be the project root")
    if _contains(dist_dir, project_root):
        raise ValueError("distribution directory must not contain the project root")
    if dist_dir.exists() and (dist_dir.is_symlink() or not dist_dir.is_dir()):
        raise ValueError("distribution directory must be a normal directory")

    _remove_generated_path(dist_dir)
    dist_dir.mkdir(parents=True, exist_ok=False)

    root_build = project_root / "build"
    _remove_generated_path(root_build / "lib")
    for path in root_build.glob("bdist.*"):
        _remove_generated_path(path)
    for path in (project_root / "src").glob("*.egg-info"):
        _remove_generated_path(path)

    for package_root in package_roots:
        package_root = Path(package_root).resolve()
        if not _contains(project_root, package_root):
            raise ValueError("workspace package root is outside the project root")
        _remove_generated_path(package_root / "build")
        for path in (package_root / "src").glob("*.egg-info"):
            _remove_generated_path(path)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", default="dist", help="Clean wheel output directory")
    parser.add_argument("--uv", default="uv", help="uv executable")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    dist_dir = Path(args.dist_dir)
    if not dist_dir.is_absolute():
        dist_dir = project_root / dist_dir
    package_roots = tuple(project_root / member for member in WORKSPACE_MEMBERS)
    try:
        clean_generated_artifacts(project_root, dist_dir, package_roots)
        command = [
            args.uv,
            "build",
            "--all-packages",
            "--wheel",
            "--out-dir",
            str(dist_dir),
        ]
        result = subprocess.run(command, cwd=str(project_root))
    except (OSError, ValueError) as exc:
        print("distribution build failed: %s" % exc, file=sys.stderr)
        return 1
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
