#!/usr/bin/env python3
"""Create a clean wheelhouse for every Python distribution in the workspace."""

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

WORKSPACE_MEMBERS = (
    "packages/embedagent-core",
    "packages/embedagent-protocol",
    "packages/embedagent-host",
    "packages/embedagent-composition",
)


REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _absolute_path(path):
    return Path(os.path.abspath(str(path)))


def _contains(parent, child):
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _is_reparse_point(path):
    status = os.lstat(str(path))
    attributes = getattr(status, "st_file_attributes", 0)
    return bool(attributes & REPARSE_POINT) or stat.S_ISLNK(status.st_mode)


def _assert_safe_generated_path(project_root, path):
    project_root = _absolute_path(project_root)
    path = _absolute_path(path)
    if not _contains(project_root, path):
        raise ValueError("generated path is outside the project root")

    current = project_root
    candidates = [current]
    for part in path.relative_to(project_root).parts:
        current = current / part
        candidates.append(current)
    for candidate in candidates:
        if os.path.lexists(str(candidate)) and _is_reparse_point(candidate):
            raise ValueError("generated path crosses a reparse point: %s" % candidate)
    return path


def _remove_generated_path(project_root, path):
    path = _assert_safe_generated_path(project_root, path)
    if not os.path.lexists(str(path)):
        return
    status = os.lstat(str(path))
    attributes = getattr(status, "st_file_attributes", 0)
    if attributes & REPARSE_POINT or stat.S_ISLNK(status.st_mode):
        raise ValueError("generated path crosses a reparse point: %s" % path)
    if stat.S_ISDIR(status.st_mode):
        shutil.rmtree(str(path))
    else:
        path.unlink()


def clean_generated_artifacts(project_root, dist_dir, package_roots):
    project_root = _absolute_path(project_root)
    dist_dir = _absolute_path(dist_dir)
    _assert_safe_generated_path(project_root, project_root)
    if dist_dir == project_root:
        raise ValueError("distribution directory must not be the project root")
    dist_dir = _assert_safe_generated_path(project_root, dist_dir)
    if os.path.lexists(str(dist_dir)):
        dist_status = os.lstat(str(dist_dir))
        if not stat.S_ISDIR(dist_status.st_mode):
            raise ValueError("distribution directory must be a normal directory")

    _remove_generated_path(project_root, dist_dir)
    dist_dir.mkdir(parents=True, exist_ok=False)

    root_build = project_root / "build"
    _assert_safe_generated_path(project_root, root_build)
    _remove_generated_path(project_root, root_build / "lib")
    for path in root_build.glob("bdist.*"):
        _remove_generated_path(project_root, path)
    _assert_safe_generated_path(project_root, project_root / "src")
    for path in (project_root / "src").glob("*.egg-info"):
        _remove_generated_path(project_root, path)

    for package_root in package_roots:
        package_root = _absolute_path(package_root)
        if not _contains(project_root, package_root):
            raise ValueError("workspace package root is outside the project root")
        _assert_safe_generated_path(project_root, package_root)
        _remove_generated_path(project_root, package_root / "build")
        _assert_safe_generated_path(project_root, package_root / "src")
        for path in (package_root / "src").glob("*.egg-info"):
            _remove_generated_path(project_root, path)


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
