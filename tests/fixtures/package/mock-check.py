#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("bundle_root")
parser.add_argument("--json-report", required=True)
args = parser.parse_args()

Path(args.json_report).write_text(
    json.dumps(
        {
            "ok": True,
            "bundle_root": args.bundle_root,
            "checks": [{"name": "mock-check", "ok": True, "errors": []}],
        },
        indent=2,
    ),
    encoding="utf-8",
)
