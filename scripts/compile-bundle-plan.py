#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "embedagent-composition" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from embedagent_composition import (  # noqa: E402
    CompositionError,
    compile_agent,
    compile_bundle_plan,
)

from embedagent.bundle_catalog import (  # noqa: E402
    official_bundle_recipe_registry,
    product_component_catalog,
)


def _canonical_json(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256(value):
    return hashlib.sha256(_canonical_json(value).encode("ascii")).hexdigest()


def _load_json(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise CompositionError("invalid_json_input", str(path))
    return payload


def _absolute(path):
    return Path(os.path.abspath(str(path)))


def _remove_generated_path(path, expected_parent):
    path = _absolute(path)
    expected_parent = _absolute(expected_parent)
    if path.parent != expected_parent:
        raise CompositionError("unsafe_generated_path", str(path))
    if not path.exists():
        return
    if path.is_symlink():
        raise CompositionError("unsafe_generated_path", str(path))
    if path.is_dir():
        shutil.rmtree(str(path))
    else:
        path.unlink()


def _write_canonical(path, payload):
    Path(path).write_text(_canonical_json(payload), encoding="ascii")


def _write_report(path, payload):
    if not path:
        return
    report_path = _absolute(path)
    if report_path.parent == report_path:
        raise CompositionError("unsafe_report_path", str(report_path))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = report_path.with_name(report_path.name + ".tmp")
    _write_canonical(temporary, payload)
    os.replace(str(temporary), str(report_path))


def _parser():
    parser = argparse.ArgumentParser(description="Compile one immutable offline bundle plan.")
    parser.add_argument("--flavor", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--assurance", required=True, choices=("dev", "release"))
    parser.add_argument("--runtime-contract", required=True)
    parser.add_argument("--asset-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--json-report", required=True)
    return parser


def _compile(args):
    recipe = official_bundle_recipe_registry().resolve(args.flavor)
    catalog = product_component_catalog()
    runtime_contract = _load_json(args.runtime_contract)
    asset_manifest = _load_json(args.asset_manifest)
    compiled_agent = compile_agent(recipe.definition_factory(), catalog)
    plan = compile_bundle_plan(
        recipe=recipe,
        catalog=catalog,
        runtime_contract=runtime_contract,
        asset_manifest=asset_manifest,
        target_id=args.target,
        assurance=args.assurance,
    )
    if _sha256(compiled_agent.lock) != plan.agent_lock_sha256:
        raise CompositionError("agent_lock_hash_mismatch", compiled_agent.agent_id)

    output_dir = _absolute(args.output_dir)
    if output_dir.parent == output_dir:
        raise CompositionError("unsafe_output_path", str(output_dir))
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_dir.with_name(output_dir.name + ".tmp")
    backup = output_dir.with_name(output_dir.name + ".old")
    _remove_generated_path(temporary, output_dir.parent)
    _remove_generated_path(backup, output_dir.parent)
    temporary.mkdir()
    try:
        _write_canonical(temporary / "agent.json", compiled_agent.manifest)
        _write_canonical(temporary / "agent.lock.json", compiled_agent.lock)
        _write_canonical(temporary / "bundle-plan.json", plan.to_dict())
        if output_dir.exists():
            output_dir.replace(backup)
        temporary.replace(output_dir)
        _remove_generated_path(backup, output_dir.parent)
    except Exception:
        if backup.exists() and not output_dir.exists():
            backup.replace(output_dir)
        _remove_generated_path(temporary, output_dir.parent)
        raise
    return plan, output_dir


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        plan, output_dir = _compile(args)
        report = {
            "ok": True,
            "flavor_id": plan.flavor_id,
            "target_id": plan.target_id,
            "assurance": plan.assurance,
            "plan_path": str(output_dir / "bundle-plan.json"),
            "plan_sha256": plan.sha256,
        }
        _write_report(args.json_report, report)
        return 0
    except CompositionError as exc:
        report = {
            "ok": False,
            "error_code": exc.code,
            "message": exc.message,
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        report = {
            "ok": False,
            "error_code": "bundle_plan_compilation_failed",
            "message": "bundle plan compilation failed",
        }
    _write_report(args.json_report, report)
    return 1


if __name__ == "__main__":
    sys.exit(main())
