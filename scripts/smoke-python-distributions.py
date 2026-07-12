#!/usr/bin/env python3
"""Install split EmbedAgent wheels into isolated Python 3.8 environments."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCENARIOS = (
    {
        "name": "core_only",
        "distribution": "embedagent-core",
        "probe": (
            "import importlib.util\n"
            "from embedagent_core import Agent\n"
            "blocked = ('embedagent_host', 'embedagent_protocol', 'embedagent')\n"
            "raise SystemExit(1 if any(importlib.util.find_spec(name) is not None "
            "for name in blocked) else 0)\n"
        ),
    },
    {
        "name": "protocol_only",
        "distribution": "embedagent-protocol",
        "probe": (
            "import importlib.util\n"
            "import embedagent_protocol\n"
            "blocked = ('embedagent_core', 'embedagent_host', 'embedagent')\n"
            "raise SystemExit(1 if any(importlib.util.find_spec(name) is not None "
            "for name in blocked) else 0)\n"
        ),
    },
    {
        "name": "host_stack",
        "distribution": "embedagent-host",
        "probe": "import embedagent_core, embedagent_protocol, embedagent_host\n",
    },
    {
        "name": "composition_only",
        "distribution": "embedagent-composition",
        "probe": "import embedagent_composition\n",
    },
)

MAX_WHEELS = 100
MAX_WHEEL_SIZE = 256 * 1024 * 1024
WHEEL_NAME = re.compile(r"^([A-Za-z0-9_.]+)-([A-Za-z0-9_.]+)(?:-[^-]+)?-[^-]+-[^-]+-[^-]+\.whl$")


def normalize_distribution_name(name):
    return re.sub(r"[-_.]+", "-", str(name or "")).lower()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", required=True, help="Directory containing checked wheels")
    parser.add_argument("--python", required=True, help="Exact Python 3.8 executable")
    parser.add_argument("--timeout", type=int, default=120, help="Per-command timeout in seconds")
    return parser.parse_args(argv)


def install_command(python_path, dist_dir, wheel_path):
    return [
        str(python_path),
        "-I",
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-cache-dir",
        "--no-index",
        "--find-links",
        str(dist_dir),
        str(wheel_path),
    ]


def _error(code, detail):
    return {"code": code, "detail": detail}


def _base_report(dist_dir, python_path):
    return {
        "schema_version": 1,
        "dist_dir": str(dist_dir),
        "python": str(python_path),
        "ok": False,
        "scenarios": [],
    }


def _wheel_distribution(path):
    match = WHEEL_NAME.fullmatch(path.name)
    if match is None:
        return ""
    return normalize_distribution_name(match.group(1))


def _discover_wheels(dist_dir):
    paths = sorted(dist_dir.glob("*.whl"), key=lambda path: path.name)
    if len(paths) > MAX_WHEELS:
        raise ValueError("wheel_count_limit")
    wheels = {}
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise ValueError("wheel_path_invalid")
        if path.stat().st_size > MAX_WHEEL_SIZE:
            raise ValueError("wheel_size_limit")
        name = _wheel_distribution(path)
        if name:
            wheels.setdefault(name, []).append(path)
    return wheels


def _run(command, timeout, environment=None):
    try:
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        return None
    except OSError:
        return False


def _command_error(result, failed_code, timeout_code):
    if result is None:
        return _error(timeout_code, "command timed out")
    if result is False:
        return _error(failed_code, "command could not be started")
    if result.returncode == 0:
        return None
    detail = "command exited with code %d" % result.returncode
    return _error(failed_code, detail)


def _venv_python(venv_root):
    if os.name == "nt":
        return venv_root / "Scripts" / "python.exe"
    return venv_root / "bin" / "python"


def _run_scenario(base_python, dist_dir, wheel_path, scenario, temp_root, timeout):
    result = {
        "name": scenario["name"],
        "distribution": scenario["distribution"],
        "wheel": wheel_path.name,
        "status": "failed",
    }
    venv_root = temp_root / scenario["name"]
    created = _run([str(base_python), "-I", "-m", "venv", str(venv_root)], timeout)
    command_error = _command_error(created, "venv_create_failed", "venv_create_timeout")
    if command_error is not None:
        result["error"] = command_error
        return result

    python_path = _venv_python(venv_root)
    environment = dict(os.environ)
    environment["PIP_NO_INDEX"] = "1"
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    installed = _run(
        install_command(python_path, dist_dir, wheel_path),
        timeout,
        environment=environment,
    )
    command_error = _command_error(installed, "wheel_install_failed", "wheel_install_timeout")
    if command_error is not None:
        result["error"] = command_error
        return result

    probed = _run([str(python_path), "-I", "-c", scenario["probe"]], timeout)
    command_error = _command_error(probed, "import_probe_failed", "import_probe_timeout")
    if command_error is not None:
        result["error"] = command_error
        return result
    result["status"] = "ok"
    return result


def build_report(dist_dir, python_path, timeout):
    dist_dir = Path(dist_dir)
    python_path = Path(python_path)
    report = _base_report(dist_dir, python_path)
    if not dist_dir.is_dir():
        report["error"] = _error("dist_dir_missing", "distribution directory was not found")
        return report
    if not python_path.is_file():
        report["error"] = _error("python_missing", "Python executable was not found")
        return report
    try:
        wheels = _discover_wheels(dist_dir)
    except (OSError, ValueError) as exc:
        code = str(exc) if str(exc) else "wheel_discovery_failed"
        report["error"] = _error(code, "wheel discovery failed")
        return report

    for scenario in SCENARIOS:
        candidates = wheels.get(normalize_distribution_name(scenario["distribution"]), [])
        if len(candidates) != 1:
            report["scenarios"].append(
                {
                    "name": scenario["name"],
                    "distribution": scenario["distribution"],
                    "wheel": "",
                    "status": "failed",
                    "error": _error("wheel_missing_or_ambiguous", "expected one wheel"),
                }
            )
    if report["scenarios"]:
        return report

    version_probe = _run(
        [
            str(python_path),
            "-I",
            "-c",
            "import sys; print('%d.%d.%d' % sys.version_info[:3]); "
            "raise SystemExit(0 if sys.version_info[:2] == (3, 8) else 1)",
        ],
        timeout,
    )
    command_error = _command_error(
        version_probe, "python_version_invalid", "python_version_probe_timeout"
    )
    if command_error is not None:
        report["error"] = command_error
        return report
    report["python_version"] = version_probe.stdout.strip()

    try:
        with tempfile.TemporaryDirectory(prefix="embedagent-wheel-smoke-") as temp_name:
            temp_root = Path(temp_name)
            for scenario in SCENARIOS:
                wheel_path = wheels[normalize_distribution_name(scenario["distribution"])][0]
                report["scenarios"].append(
                    _run_scenario(
                        python_path,
                        dist_dir,
                        wheel_path,
                        scenario,
                        temp_root,
                        timeout,
                    )
                )
    except OSError:
        report["error"] = _error("temporary_directory_failed", "temporary directory failed")
        return report
    report["ok"] = all(item["status"] == "ok" for item in report["scenarios"])
    return report


def main(argv=None):
    args = parse_args(argv)
    report = build_report(Path(args.dist_dir), Path(args.python), max(1, args.timeout))
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
