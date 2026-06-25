#!/usr/bin/env python3
"""
Validate the bundled C/C++ smoke workspace with the bundled Clang toolchain.

This is a release gate helper, not a general build system. It intentionally
compiles the tiny bundled C workspace to an object file so Windows 7 bundle
validation can prove the packaged Clang executable is usable without requiring
system SDK libraries or a network connection.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate bundled C/C++ smoke workspace.")
    parser.add_argument("--bundle-root", default="", help="Offline bundle root.")
    parser.add_argument(
        "--workspace",
        default="",
        help="Smoke workspace path. Defaults to <bundle-root>/data/workspace-template.",
    )
    parser.add_argument(
        "--clang",
        default="",
        help="Explicit clang executable for tests or diagnostics.",
    )
    parser.add_argument(
        "--allow-system-tool-fallback",
        action="store_true",
        help="Development-only fallback to PATH clang when no bundle/override clang is present.",
    )
    parser.add_argument("--json-report", default="", help="Optional JSON report path.")
    return parser


def _write_json_report(path: str, payload: Dict[str, object]) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _bundle_clang(bundle_root: str) -> str:
    if not bundle_root:
        return ""
    candidate = Path(bundle_root) / "bin" / "llvm" / "bin" / "clang.exe"
    return str(candidate) if candidate.is_file() else ""


def _resolve_clang(args: argparse.Namespace) -> Tuple[str, str]:
    override = str(args.clang or "").strip()
    if override:
        path = Path(override)
        if path.is_file():
            return str(path), "override"
        raise RuntimeError("explicit clang path not found: %s" % override)

    bundled = _bundle_clang(str(args.bundle_root or ""))
    if bundled:
        return bundled, "bundle"

    if args.allow_system_tool_fallback:
        return "clang", "system"

    raise RuntimeError("bundled clang not found and system fallback is disabled")


def _resolve_workspace(args: argparse.Namespace) -> Path:
    if args.workspace:
        workspace = Path(args.workspace)
    elif args.bundle_root:
        workspace = Path(args.bundle_root) / "data" / "workspace-template"
    else:
        raise RuntimeError("workspace is required when bundle-root is omitted")
    if not workspace.is_dir():
        raise RuntimeError("smoke workspace not found: %s" % workspace)
    source = workspace / "main.c"
    if not source.is_file():
        raise RuntimeError("smoke source not found: %s" % source)
    return workspace


def _run_command(command: List[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def run_validation(args: argparse.Namespace) -> Dict[str, object]:
    workspace = _resolve_workspace(args)
    clang, runtime_source = _resolve_clang(args)
    build_dir = workspace / ".embedagent" / "smoke-build"
    build_dir.mkdir(parents=True, exist_ok=True)
    object_path = build_dir / "main.obj"

    version_result = _run_command([clang, "--version"], workspace)
    if version_result.returncode != 0:
        raise RuntimeError(
            "clang --version failed (%s): %s"
            % (version_result.returncode, (version_result.stderr or version_result.stdout).strip())
        )

    compile_command = [
        clang,
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-c",
        str(workspace / "main.c"),
        "-o",
        str(object_path),
    ]
    compile_result = _run_command(compile_command, workspace)
    if compile_result.returncode != 0:
        raise RuntimeError(
            "clang smoke compile failed (%s): %s"
            % (
                compile_result.returncode,
                (compile_result.stderr or compile_result.stdout).strip(),
            )
        )
    if not object_path.is_file():
        raise RuntimeError("clang smoke compile did not produce object: %s" % object_path)

    return {
        "ok": True,
        "bundle_root": str(args.bundle_root or ""),
        "workspace": str(workspace),
        "clang": clang,
        "runtime_source": runtime_source,
        "allow_system_tool_fallback": bool(args.allow_system_tool_fallback),
        "source_path": str(workspace / "main.c"),
        "object_path": str(object_path),
        "clang_version": (version_result.stdout or version_result.stderr).strip(),
        "compile_command": compile_command,
    }


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    args.bundle_root = os.path.realpath(args.bundle_root) if args.bundle_root else ""
    try:
        payload = run_validation(args)
    except Exception as exc:  # pragma: no cover - command-line error path
        payload = {
            "ok": False,
            "bundle_root": str(args.bundle_root or ""),
            "workspace": str(args.workspace or ""),
            "runtime_source": "missing",
            "allow_system_tool_fallback": bool(args.allow_system_tool_fallback),
            "error": str(exc),
        }
        _write_json_report(args.json_report, payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1

    _write_json_report(args.json_report, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
