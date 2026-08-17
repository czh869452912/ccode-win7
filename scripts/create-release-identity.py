"""Write a credential-free release identity for the offline package pipeline."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from release_identity import build_release_identity, load_bundle_plan


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


def _wheel_entries(wheel_dir, expected_distributions):
    root = Path(wheel_dir)
    files = sorted(root.glob("*.whl"))
    by_distribution = {}
    for path in files:
        stem = path.name.split("-", 1)[0].replace("_", "-")
        if stem in expected_distributions:
            by_distribution[stem] = path
    if set(by_distribution) != set(expected_distributions):
        missing = sorted(set(expected_distributions) - set(by_distribution))
        raise SystemExit("wheelhouse missing planned project distributions: %s" % missing)
    return [(name, by_distribution[name]) for name in expected_distributions]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--wheel-dir", required=True)
    parser.add_argument("--bundle-plan", required=True)
    parser.add_argument("--gui-static-root")
    parser.add_argument("--asset-manifest", required=True)
    parser.add_argument("--runtime-contract", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    project_root = Path(args.project_root)
    plan = load_bundle_plan(args.bundle_plan)
    identity = build_release_identity(
        source_revision=_revision(project_root),
        version=_version(project_root),
        profile=args.profile,
        wheels=_wheel_entries(args.wheel_dir, plan["project_distribution_ids"]),
        gui_static_root=args.gui_static_root,
        asset_manifest_path=args.asset_manifest,
        runtime_contract_path=args.runtime_contract,
        bundle_plan_path=args.bundle_plan,
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
