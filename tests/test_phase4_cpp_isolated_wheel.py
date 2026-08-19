from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from embedagent_composition import compile_bundle_plan

from embedagent.bundle_catalog import official_bundle_recipe_registry, product_component_catalog

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build-python-distributions.py"
CHECKER = ROOT / "scripts" / "check-python-distributions.py"
SMOKE = ROOT / "scripts" / "smoke-python-distributions.py"
REGISTRATION_MODULE = "def register_application(registrar):\n    return lambda: None\n"


def _cpp_plan():
    return compile_bundle_plan(
        recipe=official_bundle_recipe_registry().resolve("cpp-desktop"),
        catalog=product_component_catalog(),
        runtime_contract=json.loads(
            (ROOT / "scripts" / "offline-runtime-contract.json").read_text(encoding="utf-8")
        ),
        asset_manifest=json.loads(
            (ROOT / "scripts" / "offline-assets.json").read_text(encoding="utf-8")
        ),
        target_id="win7-x64-portable",
        assurance="release",
    )


def _write_wheel(dist_dir, distribution, dependencies=(), package_files=None):
    normalized = distribution.replace("-", "_")
    wheel_path = dist_dir / (normalized + "-0.1.0-py3-none-any.whl")
    package_root = distribution.replace("-", "_")
    dist_info = normalized + "-0.1.0.dist-info"
    metadata = [
        "Metadata-Version: 2.1",
        "Name: %s" % distribution,
        "Version: 0.1.0",
    ]
    metadata.extend("Requires-Dist: %s" % dependency for dependency in dependencies)
    files = {
        package_root + "/__init__.py": b"",
        dist_info + "/METADATA": ("\n".join(metadata) + "\n").encode("utf-8"),
        dist_info
        + "/WHEEL": (
            "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
        ).encode("ascii"),
    }
    for relative_path, payload in (package_files or {}).items():
        files[package_root + "/" + relative_path] = payload.encode("utf-8")
    record_path = dist_info + "/RECORD"
    files[record_path] = "".join("%s,,\n" % name for name in list(files) + [record_path]).encode(
        "ascii"
    )
    with zipfile.ZipFile(str(wheel_path), "w") as wheel:
        for name, payload in files.items():
            wheel.writestr(name, payload)


def _checker_module():
    spec = importlib.util.spec_from_file_location("phase4_checker", str(CHECKER))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _plan_file(tmp_path, plan):
    path = tmp_path / "bundle-plan.json"
    path.write_text(json.dumps(plan.to_dict(), sort_keys=True), encoding="ascii")
    return path


def test_cpp_plan_publishes_application_scoped_runtime_and_wheel_requirements():
    plan = _cpp_plan()

    assert plan.application_runtime_requirements == (
        "runtime.python",
        "symbols.ctags",
        "toolchain.clang",
    )
    assert plan.application_project_distribution_ids == (
        "embedagent-core",
        "embedagent-protocol",
        "embedagent-workflow-cpp",
    )
    assert plan.application_registration_entries == (
        "embedagent_workflow_cpp.application:register_application",
    )


@pytest.mark.parametrize(
    "wheels",
    (
        ("embedagent-protocol", "embedagent-workflow-cpp"),
        ("embedagent-core", "embedagent-workflow-cpp"),
        ("embedagent-core", "embedagent-protocol"),
        (
            "embedagent-core",
            "embedagent-protocol",
            "embedagent-workflow-cpp",
            "embedagent-host",
        ),
        (
            "embedagent-core",
            "embedagent-protocol",
            "embedagent-workflow-cpp",
            "embedagent-shell",
        ),
    ),
)
def test_checker_rejects_non_exact_cpp_application_wheel_closure(tmp_path, wheels):
    dependencies = {
        "embedagent-core": (),
        "embedagent-protocol": (),
        "embedagent-workflow-cpp": (
            "embedagent-core ==0.1.0",
            "embedagent-protocol ==0.1.0",
        ),
        "embedagent-host": (
            "embedagent-core ==0.1.0",
            "embedagent-protocol ==0.1.0",
        ),
        "embedagent-shell": (
            "embedagent-core ==0.1.0",
            "embedagent-protocol ==0.1.0",
            "embedagent-host ==0.1.0",
        ),
    }
    for distribution in wheels:
        _write_wheel(tmp_path, distribution, dependencies[distribution])

    plan_path = _plan_file(tmp_path, _cpp_plan())
    result = subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--dist-dir",
            str(tmp_path),
            "--bundle-plan",
            str(plan_path),
            "--application-isolated",
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["ok"] is False


def test_checker_accepts_exact_cpp_application_wheel_closure(tmp_path):
    _write_wheel(tmp_path, "embedagent-core")
    _write_wheel(tmp_path, "embedagent-protocol")
    _write_wheel(
        tmp_path,
        "embedagent-workflow-cpp",
        ("embedagent-core ==0.1.0", "embedagent-protocol ==0.1.0"),
        package_files={"application.py": REGISTRATION_MODULE},
    )

    checker = _checker_module()
    plan = _cpp_plan().to_dict()
    report = checker.build_report(
        tmp_path,
        tuple(plan["project_distribution_ids"]),
        plan=plan,
        application_isolated=True,
    )

    assert report["ok"] is True
    assert report["selected_distributions"] == [
        "embedagent-core",
        "embedagent-protocol",
        "embedagent-workflow-cpp",
    ]


def test_checker_accepts_dependency_order_independent_application_closure(tmp_path):
    _write_wheel(tmp_path, "embedagent-core")
    _write_wheel(tmp_path, "embedagent-protocol")
    _write_wheel(
        tmp_path,
        "embedagent-workflow-cpp",
        ("embedagent-protocol ==0.1.0", "embedagent-core ==0.1.0"),
        package_files={"application.py": REGISTRATION_MODULE},
    )

    checker = _checker_module()
    plan = _cpp_plan().to_dict()
    report = checker.build_report(
        tmp_path,
        tuple(plan["project_distribution_ids"]),
        plan=plan,
        application_isolated=True,
    )

    assert report["ok"] is True
    assert report["derived_application_project_distribution_ids"] == [
        "embedagent-core",
        "embedagent-protocol",
        "embedagent-workflow-cpp",
    ]


def test_checker_rejects_registration_entry_without_inspected_module_owner(tmp_path):
    _write_wheel(tmp_path, "embedagent-core")
    _write_wheel(tmp_path, "embedagent-protocol")
    _write_wheel(
        tmp_path,
        "embedagent-workflow-cpp",
        ("embedagent-core ==0.1.0", "embedagent-protocol ==0.1.0"),
    )

    checker = _checker_module()
    plan = _cpp_plan().to_dict()
    report = checker.build_report(
        tmp_path,
        tuple(plan["project_distribution_ids"]),
        plan=plan,
        application_isolated=True,
    )

    assert report["ok"] is False
    assert "application_registration_owner_invalid" in {item["code"] for item in report["errors"]}


def test_checker_rejects_plan_and_wheelhouse_host_outside_entry_owner_closure(tmp_path):
    _write_wheel(tmp_path, "embedagent-core")
    _write_wheel(tmp_path, "embedagent-protocol")
    dependencies = ("embedagent-core ==0.1.0", "embedagent-protocol ==0.1.0")
    _write_wheel(
        tmp_path,
        "embedagent-workflow-cpp",
        dependencies,
        package_files={"application.py": REGISTRATION_MODULE},
    )
    _write_wheel(tmp_path, "embedagent-host", dependencies)
    plan = _cpp_plan().to_dict()
    plan["application_project_distribution_ids"].append("embedagent-host")
    plan_path = tmp_path / "bundle-plan.json"
    plan_path.write_text(json.dumps(plan, sort_keys=True), encoding="ascii")

    result = subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--dist-dir",
            str(tmp_path),
            "--bundle-plan",
            str(plan_path),
            "--application-isolated",
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert "application_distribution_closure_mismatch" in {
        item["code"] for item in report["errors"]
    }


@pytest.mark.parametrize(
    ("distribution_id", "requires", "runtime_requirements", "registration_entry"),
    (
        (
            "embedagent-host",
            ("embedagent-core", "embedagent-protocol"),
            ("runtime.python", "toolchain.clang", "symbols.ctags"),
            "embedagent_workflow_cpp.application:register_application",
        ),
        (
            "embedagent-workflow-cpp",
            ("embedagent-core",),
            ("runtime.python", "toolchain.clang", "symbols.ctags"),
            "embedagent_workflow_cpp.application:register_application",
        ),
        (
            "embedagent-workflow-cpp",
            ("embedagent-core", "embedagent-protocol"),
            ("runtime.python", "toolchain.clang"),
            "embedagent_workflow_cpp.application:register_application",
        ),
        (
            "embedagent-workflow-cpp",
            ("embedagent-core", "embedagent-protocol"),
            ("runtime.python", "toolchain.clang", "symbols.ctags"),
            "embedagent_workflow_cpp.application:register_other",
        ),
        (
            "embedagent-workflow-cpp",
            ("embedagent-core", "embedagent-protocol"),
            {
                "runtime.python": True,
                "toolchain.clang": True,
                "symbols.ctags": True,
            },
            "embedagent_workflow_cpp.application:register_application",
        ),
    ),
)
def test_isolated_smoke_rejects_installed_application_manifest_drift(
    tmp_path,
    distribution_id,
    requires,
    runtime_requirements,
    registration_entry,
):
    registration_marker = tmp_path / "registration-called.txt"
    _write_wheel(tmp_path, "embedagent-core")
    _write_wheel(tmp_path, "embedagent-protocol")
    manifest_source = """
from pathlib import Path


class Manifest(object):
    distribution_id = %r
    requires = %r
    runtime_requirements = %r
    registration_entry = %r


def cpp_application_manifest():
    return Manifest()


def register_application(registrar):
    Path(%r).write_text("called", encoding="ascii")
    return registrar.add_extension(object(), "embedagent.workflow.cpp")
""" % (
        distribution_id,
        requires,
        runtime_requirements,
        registration_entry,
        str(registration_marker),
    )
    _write_wheel(
        tmp_path,
        "embedagent-workflow-cpp",
        ("embedagent-core ==0.1.0", "embedagent-protocol ==0.1.0"),
        package_files={"application.py": manifest_source},
    )
    plan_path = _plan_file(tmp_path, _cpp_plan())

    result = subprocess.run(
        [
            sys.executable,
            str(SMOKE),
            "--dist-dir",
            str(tmp_path),
            "--python",
            sys.executable,
            "--bundle-plan",
            str(plan_path),
            "--application-isolated",
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["scenarios"][0]["error"]["code"] == "import_probe_failed"
    assert not registration_marker.exists()


def test_isolated_smoke_requires_plan_application_scope(tmp_path):
    plan = _cpp_plan().to_dict()
    plan.pop("application_project_distribution_ids")
    plan_path = tmp_path / "bundle-plan.json"
    plan_path.write_text(json.dumps(plan, sort_keys=True), encoding="ascii")
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(SMOKE),
                "--dist-dir",
                str(ROOT / "missing-wheelhouse"),
                "--python",
                sys.executable,
                "--bundle-plan",
                str(plan_path),
                "--application-isolated",
            ],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    finally:
        plan_path.unlink()

    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["error"]["code"] == "bundle_plan_invalid"


@pytest.mark.parametrize(
    ("field_name", "extra_value"),
    (
        ("application_runtime_requirements", "network.unselected"),
        ("application_registration_entries", "unselected.plugin:register_application"),
    ),
)
def test_isolated_checker_rejects_application_scope_outside_full_plan(
    tmp_path, field_name, extra_value
):
    plan = _cpp_plan().to_dict()
    plan[field_name].append(extra_value)
    plan_path = tmp_path / "bundle-plan.json"
    plan_path.write_text(json.dumps(plan, sort_keys=True), encoding="ascii")

    result = subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--dist-dir",
            str(tmp_path),
            "--bundle-plan",
            str(plan_path),
            "--application-isolated",
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["errors"][0]["code"] == "bundle_plan_invalid"


def test_cpp_application_wheels_build_and_import_offline_without_host_or_product(tmp_path):
    wheelhouse = tmp_path / "wheels"
    plan_path = _plan_file(tmp_path, _cpp_plan())
    built = subprocess.run(
        [
            sys.executable,
            str(BUILDER),
            "--dist-dir",
            str(wheelhouse),
            "--bundle-plan",
            str(plan_path),
            "--application-isolated",
            "--offline",
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert built.returncode == 0, built.stdout + built.stderr
    assert sorted(path.name.split("-", 1)[0] for path in wheelhouse.glob("*.whl")) == [
        "embedagent_core",
        "embedagent_protocol",
        "embedagent_workflow_cpp",
    ]

    smoked = subprocess.run(
        [
            sys.executable,
            str(SMOKE),
            "--dist-dir",
            str(wheelhouse),
            "--python",
            sys.executable,
            "--bundle-plan",
            str(plan_path),
            "--application-isolated",
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert smoked.returncode == 0, smoked.stdout + smoked.stderr
    report = json.loads(smoked.stdout)
    assert report["ok"] is True
    assert report["scope"] == "application"
    assert report["network_resolution"] == "disabled"
    assert report["registration_entries"] == [
        "embedagent_workflow_cpp.application:register_application"
    ]
    assert report["scenarios"] == [
        {
            "distribution": "embedagent-workflow-cpp",
            "name": "selected_application",
            "status": "ok",
            "wheel": "embedagent_workflow_cpp-0.1.0-py3-none-any.whl",
            "wheels": [
                "embedagent_core-0.1.0-py3-none-any.whl",
                "embedagent_protocol-0.1.0-py3-none-any.whl",
                "embedagent_workflow_cpp-0.1.0-py3-none-any.whl",
            ],
        }
    ]
