import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = ROOT / "scripts" / "smoke-python-distributions.py"
BUILD_SCRIPT = ROOT / "scripts" / "build-python-distributions.py"


def _load_script(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_scenarios_cover_independent_and_composed_stacks():
    smoke = _load_script(SMOKE_SCRIPT, "distribution_smoke_scenarios")

    assert [item["name"] for item in smoke.SCENARIOS] == [
        "core_only",
        "protocol_only",
        "host_stack",
        "composition_only",
    ]
    assert smoke.SCENARIOS[0]["distribution"] == "embedagent-core"
    assert smoke.SCENARIOS[2]["distribution"] == "embedagent-host"


def test_smoke_install_command_is_strictly_offline(tmp_path):
    smoke = _load_script(SMOKE_SCRIPT, "distribution_smoke_command")
    python_path = tmp_path / "venv" / "Scripts" / "python.exe"
    wheel = tmp_path / "wheels" / "embedagent_host-0.1.0-py3-none-any.whl"

    command = smoke.install_command(python_path, wheel.parent, wheel)

    assert command[:4] == [str(python_path), "-I", "-m", "pip"]
    assert "--no-index" in command
    assert "--no-cache-dir" in command
    assert command[command.index("--find-links") + 1] == str(wheel.parent)
    assert command[-1] == str(wheel)


def test_smoke_command_failures_do_not_echo_subprocess_output():
    smoke = _load_script(SMOKE_SCRIPT, "distribution_smoke_error_safety")
    completed = subprocess.CompletedProcess(
        ["python"],
        1,
        stdout="C:/random/temp/path",
        stderr="credential-or-machine-specific-output",
    )

    error = smoke._command_error(completed, "probe_failed", "probe_timeout")

    assert error == {"code": "probe_failed", "detail": "command exited with code 1"}


def test_smoke_missing_dist_directory_has_stable_json_failure(tmp_path):
    missing = tmp_path / "missing"
    command = [
        sys.executable,
        str(SMOKE_SCRIPT),
        "--dist-dir",
        str(missing),
        "--python",
        sys.executable,
    ]

    first = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True)
    second = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True)

    assert first.returncode != 0
    assert first.stderr == ""
    assert json.loads(first.stdout) == json.loads(second.stdout)
    assert json.loads(first.stdout)["error"]["code"] == "dist_dir_missing"


def test_clean_build_removes_only_generated_distribution_artifacts(tmp_path):
    builder = _load_script(BUILD_SCRIPT, "distribution_clean_build")
    project_root = tmp_path / "project"
    dist_dir = project_root / "dist"
    offline_cache = project_root / "build" / "offline-cache" / "keep.txt"
    stale_root_lib = project_root / "build" / "lib" / "stale.py"
    stale_package_build = project_root / "packages" / "one" / "build" / "stale.py"
    stale_egg_info = project_root / "src" / "old.egg-info" / "SOURCES.txt"
    stale_wheel = dist_dir / "stale.whl"
    for path in (offline_cache, stale_root_lib, stale_package_build, stale_egg_info, stale_wheel):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stale", encoding="utf-8")

    builder.clean_generated_artifacts(project_root, dist_dir, (project_root / "packages" / "one",))

    assert dist_dir.is_dir()
    assert list(dist_dir.iterdir()) == []
    assert not stale_root_lib.exists()
    assert not stale_package_build.exists()
    assert not stale_egg_info.exists()
    assert offline_cache.is_file()


def test_clean_build_rejects_project_root_as_dist_directory(tmp_path):
    builder = _load_script(BUILD_SCRIPT, "distribution_clean_build_guard")

    try:
        builder.clean_generated_artifacts(tmp_path, tmp_path, ())
    except ValueError as exc:
        assert "project root" in str(exc)
    else:
        raise AssertionError("project root must never be accepted as the distribution directory")
