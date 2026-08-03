#!/usr/bin/env python3
"""Install split EmbedAgent wheels into isolated Python 3.8 environments."""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
STANDALONE_AGENT_EXAMPLE = REPOSITORY_ROOT / "examples" / "standalone_agent.py"


def _standalone_core_probe():
    lines = [
        "import importlib.util",
        "import runpy",
        "example = runpy.run_path(%s, run_name='standalone_core_smoke')"
        % json.dumps(str(STANDALONE_AGENT_EXAMPLE)),
        'result = example["run_example"]()',
        "blocked = ('embedagent_host', 'embedagent_protocol', "
        "'embedagent_composition', 'embedagent_workflow_cpp', 'embedagent')",
        "isolated = not any(importlib.util.find_spec(name) is not None " "for name in blocked)",
        'ok = (result["waiting_reason"] == "user_input_wait" and '
        'result["interaction_kind"] == "user_input" and '
        'result["final_text"] == "done" and '
        'result["termination_reason"] == "completed" and isolated)',
        "raise SystemExit(0 if ok else 1)",
    ]
    return "\n".join(lines) + "\n"


SCENARIOS = (
    {
        "name": "core_only",
        "distribution": "embedagent-core",
        "distributions": ("embedagent-core",),
        "probe": _standalone_core_probe(),
    },
    {
        "name": "protocol_only",
        "distribution": "embedagent-protocol",
        "distributions": ("embedagent-protocol",),
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
        "distributions": ("embedagent-core", "embedagent-protocol", "embedagent-host"),
        "probe": "import embedagent_core, embedagent_protocol, embedagent_host\n",
    },
    {
        "name": "composition_only",
        "distribution": "embedagent-composition",
        "distributions": ("embedagent-composition",),
        "probe": "import embedagent_composition\n",
    },
    {
        "name": "workflow_cpp_only",
        "distribution": "embedagent-workflow-cpp",
        "distributions": ("embedagent-core", "embedagent-workflow-cpp"),
        "probe": (
            "import importlib.util\n"
            "from embedagent_workflow_cpp import cpp_runtime_definition\n"
            "blocked = ('embedagent_host', 'embedagent_protocol', 'embedagent')\n"
            "raise SystemExit(1 if any(importlib.util.find_spec(name) is not None "
            "for name in blocked) else 0)\n"
        ),
    },
    {
        "name": "product_stack",
        "distribution": "embedagent",
        "distributions": (
            "embedagent-core",
            "embedagent-protocol",
            "embedagent-host",
            "embedagent-composition",
            "embedagent-workflow-cpp",
            "embedagent",
        ),
        "probe": (
            "import os\n"
            "import sys\n"
            "import embedagent\n"
            "import embedagent_composition\n"
            "import embedagent_core\n"
            "import embedagent_host\n"
            "import embedagent_protocol\n"
            "import embedagent_workflow_cpp\n"
            "product_file = os.path.realpath(embedagent.__file__)\n"
            "venv_root = os.path.realpath(sys.prefix)\n"
            "inside_venv = os.path.commonpath((venv_root, product_file)) == venv_root\n"
            "raise SystemExit(0 if inside_venv else 1)\n"
        ),
    },
)

CHECKER_PATH = Path(__file__).resolve().parent / "check-python-distributions.py"
ALLOWED_ENVIRONMENT_KEYS = (
    "SystemRoot",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATH",
    "PATHEXT",
    "TEMP",
    "TMP",
    "TMPDIR",
    "HOME",
    "USERPROFILE",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", required=True, help="Directory containing checked wheels")
    parser.add_argument("--python", required=True, help="Exact Python 3.8 executable")
    parser.add_argument("--timeout", type=int, default=120, help="Per-command timeout in seconds")
    return parser.parse_args(argv)


def install_command(python_path, wheel_paths):
    return [
        str(python_path),
        "-I",
        "-m",
        "pip",
        "install",
        "--isolated",
        "--disable-pip-version-check",
        "--no-cache-dir",
        "--no-index",
        "--no-deps",
    ] + [str(path) for path in wheel_paths]


def minimal_environment(inherited=None):
    source = dict(os.environ if inherited is None else inherited)
    environment = {}
    for key in ALLOWED_ENVIRONMENT_KEYS:
        if key in source and source[key]:
            environment[key] = source[key]
    environment["PIP_NO_INDEX"] = "1"
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


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


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "embedagent_distribution_checker", str(CHECKER_PATH)
    )
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker


def _run(command, timeout, environment, cwd):
    try:
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env=environment,
            cwd=str(cwd),
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


def _run_scenario(base_python, wheel_paths, scenario, temp_root, timeout, environment):
    result = {
        "name": scenario["name"],
        "distribution": scenario["distribution"],
        "wheel": wheel_paths[-1].name,
        "wheels": [path.name for path in wheel_paths],
        "status": "failed",
    }
    venv_root = temp_root / scenario["name"]
    created = _run(
        [str(base_python), "-I", "-m", "venv", str(venv_root)],
        timeout,
        environment,
        temp_root,
    )
    command_error = _command_error(created, "venv_create_failed", "venv_create_timeout")
    if command_error is not None:
        result["error"] = command_error
        return result

    python_path = _venv_python(venv_root)
    installed = _run(
        install_command(python_path, wheel_paths),
        timeout,
        environment,
        temp_root,
    )
    command_error = _command_error(installed, "wheel_install_failed", "wheel_install_timeout")
    if command_error is not None:
        result["error"] = command_error
        return result

    probed = _run(
        [str(python_path), "-I", "-c", scenario["probe"]],
        timeout,
        environment,
        temp_root,
    )
    command_error = _command_error(probed, "import_probe_failed", "import_probe_timeout")
    if command_error is not None:
        result["error"] = command_error
        return result
    result["status"] = "ok"
    return result


def build_report(dist_dir, python_path, timeout):
    dist_dir = Path(os.path.abspath(str(dist_dir)))
    python_path = Path(os.path.abspath(str(python_path)))
    report = _base_report(dist_dir, python_path)
    if not dist_dir.is_dir():
        report["error"] = _error("dist_dir_missing", "distribution directory was not found")
        return report
    if not python_path.is_file():
        report["error"] = _error("python_missing", "Python executable was not found")
        return report
    checker_report = _load_checker().build_report(dist_dir)
    if not checker_report["ok"] or len(checker_report["verified_wheels"]) != 6:
        report["error"] = _error(
            "distribution_check_failed", "wheelhouse failed exact distribution validation"
        )
        return report
    verified_paths = [dist_dir / name for name in checker_report["verified_wheels"]]
    wheels = {}
    for distribution, path in zip(
        (
            "embedagent-core",
            "embedagent-protocol",
            "embedagent-host",
            "embedagent-composition",
            "embedagent-workflow-cpp",
            "embedagent",
        ),
        verified_paths,
    ):
        wheels[distribution] = path
    environment = minimal_environment()

    try:
        with tempfile.TemporaryDirectory(prefix="embedagent-wheel-smoke-") as temp_name:
            temp_root = Path(temp_name)
            version_probe = _run(
                [
                    str(python_path),
                    "-I",
                    "-c",
                    "import sys; print('%d.%d.%d' % sys.version_info[:3]); "
                    "raise SystemExit(0 if sys.version_info[:2] == (3, 8) else 1)",
                ],
                timeout,
                environment,
                temp_root,
            )
            command_error = _command_error(
                version_probe, "python_version_invalid", "python_version_probe_timeout"
            )
            if command_error is not None:
                report["error"] = command_error
                return report
            report["python_version"] = version_probe.stdout.strip()
            for scenario in SCENARIOS:
                wheel_paths = [wheels[name] for name in scenario["distributions"]]
                report["scenarios"].append(
                    _run_scenario(
                        python_path,
                        wheel_paths,
                        scenario,
                        temp_root,
                        timeout,
                        environment,
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
