#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--json-report", required=True)
parser.add_argument("--output-dir", required=False, default="")
parser.add_argument("--cache-dir", required=False, default="")
parser.add_argument("--offline", action="store_true")
parser.add_argument("--bundle-plan", required=True)
parser.add_argument("--bundle-plan-sha256", required=True)
args = parser.parse_args()

plan_path = Path(args.bundle_plan)
plan = json.loads(plan_path.read_text(encoding="ascii"))
plan_hash = hashlib.sha256(plan_path.read_bytes()).hexdigest()
if plan_hash != args.bundle_plan_sha256:
    raise ValueError("bundle plan hash mismatch")

distributions = list(plan["project_distribution_ids"])
wheels = [name.replace("-", "_") + "-0.1.0-py3-none-any.whl" for name in distributions]

if args.output_dir:
    (Path(args.output_dir) / "site-packages").mkdir(parents=True, exist_ok=True)

Path(args.json_report).write_text(
    json.dumps(
        {
            "ok": True,
            "mode": "export",
            "output_dir": args.output_dir,
            "missing_packages": [],
            "flavor_id": plan["flavor_id"],
            "bundle_plan_sha256": plan_hash,
            "python_feature_ids": plan["python_feature_ids"],
            "project_distributions": distributions,
            "project_wheels": wheels,
            "wheel_hashes": dict((name, "a" * 64) for name in wheels),
        },
        indent=2,
    ),
    encoding="utf-8",
)
