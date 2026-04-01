#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--json-report", required=True)
parser.add_argument("--output-dir", required=False, default="")
args = parser.parse_args()

Path(args.json_report).write_text(
    json.dumps(
        {
            "ok": True,
            "mode": "export",
            "output_dir": args.output_dir,
            "missing_packages": [],
        },
        indent=2,
    ),
    encoding="utf-8",
)
