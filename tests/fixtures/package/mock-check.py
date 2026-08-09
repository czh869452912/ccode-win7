#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("bundle_root")
parser.add_argument("--bundle-plan", required=True)
parser.add_argument("--bundle-plan-sha256", required=True)
parser.add_argument("--json-report", required=True)
args = parser.parse_args()
plan_path = Path(args.bundle_plan)
actual_plan_sha256 = hashlib.sha256(plan_path.read_bytes()).hexdigest()
if actual_plan_sha256 != args.bundle_plan_sha256.lower():
    raise SystemExit("mock check bundle plan hash mismatch")

Path(args.json_report).write_text(
    json.dumps(
        {
            "ok": True,
            "bundle_root": args.bundle_root,
            "checks": [{"name": "mock-check", "ok": True, "errors": []}],
            "bundle_plan": {
                "path": str(plan_path),
                "source_path": str(plan_path),
                "sha256": actual_plan_sha256,
            },
        },
        indent=2,
    ),
    encoding="utf-8",
)
