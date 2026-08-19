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

try:
    from bundle_plan import load_bundle_plan, normalize_distribution_name
except ImportError:  # pragma: no cover - module loading by a test harness
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from bundle_plan import load_bundle_plan, normalize_distribution_name

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
        "distributions": (
            "embedagent-core",
            "embedagent-protocol",
            "embedagent-workflow-cpp",
        ),
        "probe": (
            "import importlib.util\n"
            "from embedagent_workflow_cpp import cpp_runtime_definition\n"
            "blocked = ('embedagent_host', 'embedagent_composition', 'embedagent')\n"
            "raise SystemExit(1 if any(importlib.util.find_spec(name) is not None "
            "for name in blocked) else 0)\n"
        ),
    },
    {
        "name": "product_stack",
        "distribution": "embedagent-shell",
        "distributions": (
            "embedagent-core",
            "embedagent-protocol",
            "embedagent-host",
            "embedagent-shell",
        ),
        "probe": (
            "import os\n"
            "import sys\n"
            "import embedagent\n"
            "import embedagent_core\n"
            "import embedagent_host\n"
            "import embedagent_protocol\n"
            "from embedagent.cli import build_parser\n"
            "product_file = os.path.realpath(embedagent.__file__)\n"
            "venv_root = os.path.realpath(sys.prefix)\n"
            "inside_venv = os.path.commonpath((venv_root, product_file)) == venv_root\n"
            'run = build_parser().parse_args(["run", "smoke"])\n'
            'chat = build_parser().parse_args(["chat"])\n'
            'sessions = build_parser().parse_args(["sessions", "list"])\n'
            "cli_ok = run.command == 'run' and chat.command == 'chat' "
            "and sessions.sessions_action == 'list'\n"
            "raise SystemExit(0 if inside_venv and cli_ok else 1)\n"
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
    parser.add_argument("--bundle-plan", default="", help="Compiled bundle plan JSON")
    parser.add_argument(
        "--application-isolated",
        action="store_true",
        help="Probe only the plan-selected application runtime wheel closure",
    )
    return parser.parse_args(argv)


def scenario_wheels(distributions, plan, field_name="project_distribution_ids"):
    selected = {normalize_distribution_name(item) for item in (plan.get(field_name) or ())}
    requested = tuple(str(item or "").strip() for item in distributions)
    unplanned = [item for item in requested if normalize_distribution_name(item) not in selected]
    if unplanned:
        raise ValueError("unplanned distribution: %s" % unplanned[0])
    return requested


def _plan_scenario(plan):
    distributions = tuple(plan.get("project_distribution_ids") or ())
    return {
        "name": "selected_product",
        "distribution": distributions[-1],
        "distributions": scenario_wheels(distributions, plan),
        "probe": (
            "import os\n"
            "import sys\n"
            "import embedagent\n"
            "from embedagent.cli import build_parser\n"
            "product_file = os.path.realpath(embedagent.__file__)\n"
            "venv_root = os.path.realpath(sys.prefix)\n"
            "inside_venv = os.path.commonpath((venv_root, product_file)) == venv_root\n"
            'run = build_parser().parse_args(["run", "smoke"])\n'
            'chat = build_parser().parse_args(["chat"])\n'
            'sessions = build_parser().parse_args(["sessions", "list"])\n'
            "cli_ok = run.command == 'run' and chat.command == 'chat' "
            "and sessions.sessions_action == 'list'\n"
            "raise SystemExit(0 if inside_venv and cli_ok else 1)\n"
        ),
    }


def _application_probe(plan, registration_owner):
    distributions = tuple(plan.get("application_project_distribution_ids") or ())
    import_roots = tuple(
        normalize_distribution_name(item).replace("-", "_") for item in distributions
    )
    entries = tuple(plan.get("application_registration_entries") or ())
    if not import_roots or not entries:
        raise ValueError("bundle plan application runtime scope is required")
    lines = [
        "import importlib",
        "import importlib.util",
        "selected = %s" % repr(import_roots),
        "planned_distributions = %s" % repr(distributions),
        "planned_requirements = %s"
        % repr(tuple(plan.get("application_runtime_requirements") or ())),
        "planned_entries = %s" % repr(entries),
        "registration_owner = %s" % json.dumps(registration_owner),
        "modules = [importlib.import_module(name) for name in selected]",
        "blocked = ('embedagent_host', 'embedagent_composition', 'embedagent')",
        "isolated = not any(importlib.util.find_spec(name) is not None for name in blocked)",
        "disposed = []",
        "sources = []",
        "class Registrar(object):",
        "    def _add(self, _value, source_id):",
        "        sources.append(source_id)",
        "        def dispose():",
        "            disposed.append(source_id)",
        "        return dispose",
        "    add_runtime_contribution = _add",
        "    add_extension = _add",
        "    add_prompt_provider = _add",
        "    add_context_provider = _add",
        "    add_shell_contribution = _add",
        "registrar = Registrar()",
        "entry_modules = []",
        "entry_callables = []",
    ]
    for entry in entries:
        module_name, separator, callable_name = str(entry or "").partition(":")
        if not separator or not module_name or not callable_name:
            raise ValueError("bundle plan application registration entry is invalid")
        lines.extend(
            (
                "entry_module = importlib.import_module(%s)" % json.dumps(module_name),
                "entry_modules.append(entry_module)",
                "entry_callable = getattr(entry_module, %s, None)" % json.dumps(callable_name),
                "entry_callables.append(entry_callable)",
            )
        )
    lines.extend(
        (
            "manifest_module = entry_modules[0] if len(entry_modules) == 1 else None",
            "manifest_factory = getattr(manifest_module, 'application_manifest', None) if manifest_module else None",
            "if not callable(manifest_factory) and manifest_module:",
            "    manifest_factory = getattr(manifest_module, 'cpp_application_manifest', None)",
            "manifest = manifest_factory() if callable(manifest_factory) else None",
            "def manifest_field(name):",
            "    if isinstance(manifest, dict):",
            "        return manifest.get(name)",
            "    return getattr(manifest, name, None)",
            "def names(values):",
            "    if not isinstance(values, (list, tuple)):",
            "        return ()",
            "    return tuple(sorted(str(value).replace('_', '-').replace('.', '-').lower() for value in values))",
            "manifest_requires = manifest_field('requires')",
            "manifest_runtime_requirements = manifest_field('runtime_requirements')",
            "manifest_distribution = str(manifest_field('distribution_id') or '')",
            "manifest_dependencies = names(manifest_requires)",
            "manifest_requirements = tuple(sorted(str(value) for value in manifest_runtime_requirements)) if isinstance(manifest_runtime_requirements, (list, tuple)) else ()",
            "manifest_entry = str(manifest_field('registration_entry') or '')",
            "expected_dependencies = names(tuple(item for item in planned_distributions if item != registration_owner))",
            "manifest_contract_ok = (",
            "    bool(registration_owner)",
            "    and isinstance(manifest_requires, (list, tuple))",
            "    and isinstance(manifest_runtime_requirements, (list, tuple))",
            "    and manifest_distribution.replace('_', '-').replace('.', '-').lower() == registration_owner.replace('_', '-').replace('.', '-').lower()",
            "    and manifest_dependencies == expected_dependencies",
            "    and manifest_requirements == tuple(sorted(planned_requirements))",
            "    and len(planned_entries) == 1",
            "    and manifest_entry == planned_entries[0]",
            ")",
            "if not manifest_contract_ok:",
            "    raise SystemExit(1)",
            "registration_disposers = [entry_callable(registrar) if callable(entry_callable) else None for entry_callable in entry_callables]",
            "valid_disposers = all(callable(item) for item in registration_disposers)",
            "for item in reversed(registration_disposers):",
            "    if callable(item):",
            "        item()",
            "source_aware = bool(sources) and all(bool(str(source).strip()) for source in sources)",
            "disposed_all = len(disposed) == len(sources)",
            "raise SystemExit(0 if isolated and modules and valid_disposers and source_aware and disposed_all else 1)",
        )
    )
    return "\n".join(lines) + "\n"


def _application_scenario(plan, registration_owner):
    distributions = tuple(plan.get("application_project_distribution_ids") or ())
    return {
        "name": "selected_application",
        "distribution": registration_owner,
        "distributions": scenario_wheels(
            distributions,
            plan,
            field_name="application_project_distribution_ids",
        ),
        "probe": _application_probe(plan, registration_owner),
    }


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
            encoding="utf-8",
            errors="replace",
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


def build_report(
    dist_dir,
    python_path,
    timeout,
    selected_distributions=None,
    plan=None,
    application_isolated=False,
):
    dist_dir = Path(os.path.abspath(str(dist_dir)))
    python_path = Path(os.path.abspath(str(python_path)))
    report = _base_report(dist_dir, python_path)
    if not dist_dir.is_dir():
        report["error"] = _error("dist_dir_missing", "distribution directory was not found")
        return report
    if not python_path.is_file():
        report["error"] = _error("python_missing", "Python executable was not found")
        return report
    checker_report = _load_checker().build_report(
        dist_dir,
        selected_distributions,
        plan=plan,
        application_isolated=application_isolated,
    )
    if not checker_report["ok"]:
        report["error"] = _error(
            "distribution_check_failed", "wheelhouse failed exact distribution validation"
        )
        return report
    wheels = {}
    for item in checker_report["distributions"]:
        wheels[item["name"]] = dist_dir / item["wheel"]
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
            if application_isolated:
                scenarios = [
                    _application_scenario(
                        plan,
                        checker_report["application_registration_owner"],
                    )
                ]
            else:
                scenarios = [_plan_scenario(plan)] if plan is not None else SCENARIOS
            for scenario in scenarios:
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
    if application_isolated:
        report["scope"] = "application"
        report["network_resolution"] = "disabled"
        report["runtime_requirements"] = list(plan["application_runtime_requirements"])
        report["registration_entries"] = list(plan["application_registration_entries"])
    return report


def main(argv=None):
    args = parse_args(argv)
    try:
        if args.application_isolated and not args.bundle_plan:
            raise ValueError("application-isolated smoke requires a bundle plan")
        plan = None
        selected = None
        if args.bundle_plan:
            plan, selected = load_bundle_plan(
                args.bundle_plan,
                application_isolated=args.application_isolated,
            )
        report = build_report(
            Path(args.dist_dir),
            Path(args.python),
            max(1, args.timeout),
            selected_distributions=selected,
            plan=plan,
            application_isolated=args.application_isolated,
        )
    except ValueError as exc:
        report = _base_report(Path(args.dist_dir), Path(args.python))
        report["error"] = _error("bundle_plan_invalid", str(exc))
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
