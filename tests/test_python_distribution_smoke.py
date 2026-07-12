import importlib.util
import json
import os
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = ROOT / "scripts" / "smoke-python-distributions.py"
BUILD_SCRIPT = ROOT / "scripts" / "build-python-distributions.py"
EXPORT_SCRIPT = ROOT / "scripts" / "export-dependencies.py"


def _load_script(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_junction(link, target):
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "New-Item -ItemType Junction -Path '{0}' -Target '{1}' | Out-Null".format(
                str(link).replace("'", "''"), str(target).replace("'", "''")
            ),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("junction creation failed: %s" % result.stderr)


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
    assert smoke.SCENARIOS[2]["distributions"] == (
        "embedagent-core",
        "embedagent-protocol",
        "embedagent-host",
    )


def test_smoke_install_command_is_strictly_offline(tmp_path):
    smoke = _load_script(SMOKE_SCRIPT, "distribution_smoke_command")
    python_path = tmp_path / "venv" / "Scripts" / "python.exe"
    wheels = [
        (tmp_path / "wheels" / name).resolve()
        for name in (
            "embedagent_core-0.1.0-py3-none-any.whl",
            "embedagent_protocol-0.1.0-py3-none-any.whl",
            "embedagent_host-0.1.0-py3-none-any.whl",
        )
    ]

    command = smoke.install_command(python_path, wheels)

    assert command[:4] == [str(python_path), "-I", "-m", "pip"]
    assert "--no-index" in command
    assert "--no-deps" in command
    assert "--no-cache-dir" in command
    assert "--find-links" not in command
    assert command[-3:] == [str(path) for path in wheels]


def test_smoke_minimal_environment_removes_controls_and_credentials():
    smoke = _load_script(SMOKE_SCRIPT, "distribution_smoke_environment")
    inherited = {
        "SystemRoot": r"C:\Windows",
        "PATH": r"C:\Windows\System32",
        "TEMP": r"C:\Temp",
        "PIP_FIND_LINKS": r"C:\foreign-wheels",
        "PIP_INDEX_URL": "https://user:secret@example.invalid/simple",
        "PYTHONPATH": r"C:\credential-module",
        "PYTHONSTARTUP": r"C:\steal.py",
        "OPENAI_API_KEY": "top-secret",
        "GITHUB_TOKEN": "top-secret",
    }

    environment = smoke.minimal_environment(inherited)

    assert environment["SystemRoot"] == r"C:\Windows"
    assert environment["PATH"] == r"C:\Windows\System32"
    assert environment["PIP_NO_INDEX"] == "1"
    assert environment["PIP_DISABLE_PIP_VERSION_CHECK"] == "1"
    assert environment["PYTHONNOUSERSITE"] == "1"
    assert "PIP_FIND_LINKS" not in environment
    assert "PIP_INDEX_URL" not in environment
    assert "PYTHONPATH" not in environment
    assert "PYTHONSTARTUP" not in environment
    assert "OPENAI_API_KEY" not in environment
    assert "GITHUB_TOKEN" not in environment


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


@unittest.skipIf(sys.platform != "win32", "Windows-only reparse-point contract")
def test_clean_build_rejects_dist_junction_without_touching_target(tmp_path):
    builder = _load_script(BUILD_SCRIPT, "distribution_clean_dist_junction")
    project_root = tmp_path / "project"
    project_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_text("keep", encoding="ascii")
    dist_junction = project_root / "dist"
    _create_junction(dist_junction, outside)
    try:
        try:
            builder.clean_generated_artifacts(project_root, dist_junction, ())
        except ValueError as exc:
            assert "reparse point" in str(exc)
        else:
            raise AssertionError("distribution junction must be rejected")
        assert sentinel.read_text(encoding="ascii") == "keep"
    finally:
        if dist_junction.exists():
            os.rmdir(str(dist_junction))


@unittest.skipIf(sys.platform != "win32", "Windows-only reparse-point contract")
def test_clean_build_rejects_package_build_junction_without_touching_target(tmp_path):
    builder = _load_script(BUILD_SCRIPT, "distribution_clean_package_junction")
    project_root = tmp_path / "project"
    package_root = project_root / "packages" / "one"
    package_root.mkdir(parents=True)
    outside = tmp_path / "outside-package-build"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_text("keep", encoding="ascii")
    build_junction = package_root / "build"
    _create_junction(build_junction, outside)
    try:
        try:
            builder.clean_generated_artifacts(project_root, project_root / "dist", (package_root,))
        except ValueError as exc:
            assert "reparse point" in str(exc)
        else:
            raise AssertionError("package build junction must be rejected")
        assert sentinel.read_text(encoding="ascii") == "keep"
    finally:
        if build_junction.exists():
            os.rmdir(str(build_junction))


def test_clean_build_resets_external_flat_wheelhouse_without_removing_directory(tmp_path):
    builder = _load_script(BUILD_SCRIPT, "distribution_clean_external")
    project_root = tmp_path / "project"
    project_root.mkdir()
    external = tmp_path / "external-wheelhouse"
    external.mkdir()
    stale_wheel = external / "stale-0.1.0-py3-none-any.whl"
    stale_wheel.write_bytes(b"stale")
    alongside = tmp_path / "keep.txt"
    alongside.write_text("keep", encoding="ascii")

    builder.clean_generated_artifacts(project_root, external, ())

    assert external.is_dir()
    assert list(external.iterdir()) == []
    assert alongside.read_text(encoding="ascii") == "keep"


def test_clean_build_refuses_unexpected_external_content_without_deleting_anything(tmp_path):
    builder = _load_script(BUILD_SCRIPT, "distribution_clean_external_unexpected")
    project_root = tmp_path / "project"
    project_root.mkdir()
    external = tmp_path / "external-wheelhouse"
    external.mkdir()
    stale_wheel = external / "stale-0.1.0-py3-none-any.whl"
    unexpected = external / "keep.txt"
    stale_wheel.write_bytes(b"stale")
    unexpected.write_text("keep", encoding="ascii")

    try:
        builder.clean_generated_artifacts(project_root, external, ())
    except ValueError as exc:
        assert "unexpected entry" in str(exc)
    else:
        raise AssertionError("unexpected external wheelhouse content must be refused")

    assert stale_wheel.read_bytes() == b"stale"
    assert unexpected.read_text(encoding="ascii") == "keep"


def test_clean_build_rejects_external_ancestor_of_project_without_deletion(tmp_path):
    builder = _load_script(BUILD_SCRIPT, "distribution_clean_external_ancestor")
    project_root = tmp_path / "project"
    project_root.mkdir()
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("keep", encoding="ascii")

    try:
        builder.clean_generated_artifacts(project_root, tmp_path, ())
    except ValueError as exc:
        assert "contain the project root" in str(exc)
    else:
        raise AssertionError("project ancestor must never be a distribution directory")

    assert sentinel.read_text(encoding="ascii") == "keep"


@unittest.skipIf(sys.platform != "win32", "Windows-only reparse-point contract")
def test_clean_build_rejects_external_junction_without_touching_target(tmp_path):
    builder = _load_script(BUILD_SCRIPT, "distribution_clean_external_junction")
    project_root = tmp_path / "project"
    project_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_text("keep", encoding="ascii")
    junction = tmp_path / "external-junction"
    _create_junction(junction, outside)
    try:
        try:
            builder.clean_generated_artifacts(project_root, junction, ())
        except ValueError as exc:
            assert "reparse point" in str(exc)
        else:
            raise AssertionError("external wheelhouse junction must be rejected")
        assert sentinel.read_text(encoding="ascii") == "keep"
    finally:
        if junction.exists():
            os.rmdir(str(junction))


def test_external_wheelhouse_build_check_and_smoke_preserve_siblings(tmp_path):
    external = tmp_path / "external-wheelhouse"
    sibling = tmp_path / "keep.txt"
    sibling.write_text("keep", encoding="ascii")
    build = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--dist-dir", str(external)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    check = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "check-python-distributions.py"),
            "--dist-dir",
            str(external),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert check.returncode == 0, check.stdout + check.stderr
    smoke = subprocess.run(
        [
            sys.executable,
            str(SMOKE_SCRIPT),
            "--dist-dir",
            str(external),
            "--python",
            sys.executable,
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    assert len(list(external.glob("*.whl"))) == 5
    assert sibling.read_text(encoding="ascii") == "keep"


def test_export_dependencies_supports_external_output_directory(tmp_path, monkeypatch):
    exporter = _load_script(EXPORT_SCRIPT, "distribution_external_export")
    output = tmp_path / "external-export"
    sibling = tmp_path / "keep.txt"
    sibling.write_text("keep", encoding="ascii")
    monkeypatch.setattr(exporter, "get_all_dependencies", lambda _root: [])
    original_run = exporter._run

    def run_without_third_party_install(command, cwd=None, check=True):
        if "--requirement" in command:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        return original_run(command, cwd=cwd, check=check)

    monkeypatch.setattr(exporter, "_run", run_without_third_party_install)

    exporter.export_site_packages(str(ROOT), str(output), "3.8")

    assert len(list((output / "wheels").glob("*.whl"))) == 5
    for package_name in (
        "embedagent",
        "embedagent_core",
        "embedagent_protocol",
        "embedagent_host",
        "embedagent_composition",
    ):
        assert (output / "site-packages" / package_name).is_dir()
    assert sibling.read_text(encoding="ascii") == "keep"


def _write_installable_wheel(
    dist_dir, distribution, package_name, package_body="", dependencies=(), build_tag=""
):
    filename_distribution = distribution.replace("-", "_")
    build_part = ("-" + build_tag) if build_tag else ""
    wheel_path = dist_dir / ("%s-0.1.0%s-py3-none-any.whl" % (filename_distribution, build_part))
    dist_info = "%s-0.1.0.dist-info" % filename_distribution
    metadata_lines = [
        "Metadata-Version: 2.1",
        "Name: %s" % distribution,
        "Version: 0.1.0",
    ]
    metadata_lines.extend("Requires-Dist: %s" % item for item in dependencies)
    files = {
        package_name + "/__init__.py": package_body.encode("utf-8"),
        dist_info + "/METADATA": ("\n".join(metadata_lines) + "\n").encode("utf-8"),
        dist_info
        + "/WHEEL": (
            "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
        ).encode("ascii"),
    }
    record_path = dist_info + "/RECORD"
    record = "".join("%s,,\n" % name for name in list(files) + [record_path])
    files[record_path] = record.encode("ascii")
    with zipfile.ZipFile(str(wheel_path), "w") as wheel:
        for name, payload in files.items():
            wheel.writestr(name, payload)
    return wheel_path


def _write_installable_distribution_set(dist_dir):
    _write_installable_wheel(
        dist_dir,
        "embedagent-core",
        "embedagent_core",
        "class Agent:\n    pass\n",
    )
    _write_installable_wheel(dist_dir, "embedagent-protocol", "embedagent_protocol")
    _write_installable_wheel(
        dist_dir,
        "embedagent-host",
        "embedagent_host",
        dependencies=("embedagent-core ==0.1.0", "embedagent-protocol ==0.1.0"),
    )
    _write_installable_wheel(dist_dir, "embedagent-composition", "embedagent_composition")
    _write_installable_wheel(dist_dir, "embedagent", "embedagent")


def test_smoke_ignores_foreign_pip_links_python_controls_and_credentials(tmp_path):
    dist_dir = tmp_path / "dist"
    foreign_dir = tmp_path / "foreign"
    credential_dir = tmp_path / "credential-module"
    dist_dir.mkdir()
    foreign_dir.mkdir()
    credential_dir.mkdir()
    _write_installable_distribution_set(dist_dir)
    foreign_sentinel = tmp_path / "foreign-imported.txt"
    credential_sentinel = tmp_path / "credential-imported.txt"
    _write_installable_wheel(
        foreign_dir,
        "embedagent-core",
        "embedagent_core",
        "open({0}, 'w').write('foreign')\nraise RuntimeError('foreign wheel selected')\n".format(
            repr(str(foreign_sentinel))
        ),
        build_tag="99",
    )
    credential_package = credential_dir / "embedagent_protocol"
    credential_package.mkdir()
    (credential_package / "__init__.py").write_text(
        "open({0}, 'w').write('credential')\n".format(repr(str(credential_sentinel))),
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PIP_FIND_LINKS"] = str(foreign_dir)
    environment["PIP_INDEX_URL"] = "https://user:do-not-leak@example.invalid/simple"
    environment["PYTHONPATH"] = str(credential_dir)
    environment["OPENAI_API_KEY"] = "credential-do-not-leak"
    result = subprocess.run(
        [
            sys.executable,
            str(SMOKE_SCRIPT),
            "--dist-dir",
            str(dist_dir),
            "--python",
            sys.executable,
        ],
        cwd=str(ROOT),
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ok"] is True
    assert not foreign_sentinel.exists()
    assert not credential_sentinel.exists()
    assert "do-not-leak" not in result.stdout
    assert "do-not-leak" not in result.stderr
