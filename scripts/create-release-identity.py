"""Write a credential-free release identity for the offline package pipeline."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from release_identity import EXPECTED_DISTRIBUTIONS, build_release_identity


def _revision(project_root):
    try:
        output = subprocess.check_output(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit("unable to resolve source revision: %s" % exc)
    return output.strip()


def _version(project_root):
    pyproject = (Path(project_root) / "pyproject.toml").read_text(encoding="utf-8")
    for line in pyproject.splitlines():
        if line.strip().startswith("version") and "=" in line:
            value = line.split("=", 1)[1].strip().strip("\"'")
            if value:
                return value
    raise SystemExit("project version not found in pyproject.toml")


def _wheel_entries(wheel_dir):
    root = Path(wheel_dir)
    files = sorted(root.glob("*.whl"))
    by_distribution = {}
    for path in files:
        stem = path.name.split("-", 1)[0].replace("_", "-")
        if stem in EXPECTED_DISTRIBUTIONS:
            by_distribution[stem] = path
    if set(by_distribution) != set(EXPECTED_DISTRIBUTIONS):
        missing = sorted(set(EXPECTED_DISTRIBUTIONS) - set(by_distribution))
        raise SystemExit("wheelhouse missing exact project distributions: %s" % missing)
    return [(name, by_distribution[name]) for name in EXPECTED_DISTRIBUTIONS]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--wheel-dir", required=True)
    parser.add_argument("--gui-static-root", required=True)
    parser.add_argument("--asset-manifest", required=True)
    parser.add_argument("--runtime-contract", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    project_root = Path(args.project_root)
    identity = build_release_identity(
        source_revision=_revision(project_root),
        version=_version(project_root),
        profile=args.profile,
        wheels=_wheel_entries(args.wheel_dir),
        gui_static_root=args.gui_static_root,
        asset_manifest_path=args.asset_manifest,
        runtime_contract_path=args.runtime_contract,
        tool_metadata={"identity_tool": "scripts/create-release-identity.py"},
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(identity, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="ascii",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
