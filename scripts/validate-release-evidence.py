"""Validate a hash-bound Win7 target evidence report offline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from release_identity import canonical_json


def identity_sha256(identity):
    import hashlib

    return hashlib.sha256(canonical_json(identity).encode("ascii")).hexdigest()


def _check(checks, blocking_errors, code, condition):
    item = {"code": code, "ok": bool(condition)}
    checks.append(item)
    if not condition:
        blocking_errors.append(code)


def validate_report(identity, report):
    checks = []
    blocking_errors = []
    if not isinstance(report, dict):
        return {"status": "NOT_READY", "checks": [], "blocking_errors": ["report.object"]}
    _check(checks, blocking_errors, "report.schema_version", report.get("schema_version") == 1)
    _check(
        checks,
        blocking_errors,
        "release_identity.sha256",
        report.get("release_identity_sha256") == identity_sha256(identity),
    )
    machine = report.get("machine")
    _check(checks, blocking_errors, "machine.missing", isinstance(machine, dict))
    if isinstance(machine, dict):
        _check(
            checks,
            blocking_errors,
            "machine.os_name",
            machine.get("os_name") == "Microsoft Windows 7",
        )
        _check(checks, blocking_errors, "machine.service_pack", machine.get("service_pack") == "SP1")
        _check(checks, blocking_errors, "machine.architecture", machine.get("architecture") == "AMD64")
    gui = report.get("gui")
    _check(checks, blocking_errors, "gui.missing", isinstance(gui, dict))
    if isinstance(gui, dict):
        _check(checks, blocking_errors, "gui.renderer", gui.get("renderer") == "edgechromium")
        _check(checks, blocking_errors, "gui.runtime_source", gui.get("runtime_source") == "bundle")
        _check(checks, blocking_errors, "gui.webview2_major", gui.get("webview2_major") == 109)
        _check(
            checks,
            blocking_errors,
            "gui.fixed_runtime_exists",
            gui.get("fixed_runtime_exists") is True,
        )
    cpp = report.get("cpp")
    _check(checks, blocking_errors, "cpp.missing", isinstance(cpp, dict))
    if isinstance(cpp, dict):
        _check(checks, blocking_errors, "cpp.ok", cpp.get("ok") is True)
        _check(checks, blocking_errors, "cpp.runtime_source", cpp.get("runtime_source") == "bundle")
        _check(
            checks,
            blocking_errors,
            "cpp.system_tool_fallback",
            cpp.get("allow_system_tool_fallback") is False,
        )
    _check(
        checks,
        blocking_errors,
        "blocking_errors.empty",
        report.get("blocking_errors") == [],
    )
    status = "ACCEPTED" if not blocking_errors else "NOT_READY"
    return {
        "status": status,
        "release_identity_sha256": identity_sha256(identity),
        "checks": checks,
        "blocking_errors": blocking_errors,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--json-report", required=True)
    args = parser.parse_args(argv)
    identity = json.loads(Path(args.identity).read_text(encoding="utf-8"))
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    result = validate_report(identity, report)
    Path(args.json_report).write_text(
        json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["status"] == "ACCEPTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())

