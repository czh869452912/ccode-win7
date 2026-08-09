import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_identity.py"
CREATE_SCRIPT = ROOT / "scripts" / "create-release-identity.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("release_identity_test_module", str(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wheels(tmp_path):
    names = (
        "embedagent-core",
        "embedagent-protocol",
        "embedagent-host",
        "embedagent-composition",
        "embedagent-workflow-cpp",
        "embedagent",
    )
    wheels = []
    for name in names:
        path = tmp_path / (name.replace("-", "_") + "-0.1.0-py3-none-any.whl")
        path.write_bytes(name.encode("ascii"))
        wheels.append((name, path))
    return wheels


def _bundle_plan(tmp_path, *, flavor_id="minimal-cli", gui=False):
    path = tmp_path / (flavor_id + "-bundle-plan.json")
    plan = {
        "schema_version": 1,
        "flavor_id": flavor_id,
        "target_id": "win7-x64-portable",
        "agent_lock_sha256": "f" * 64,
        "shell_ids": ["cli", "tui", "gui"] if gui else ["cli"],
        "gate_ids": (
            [
                "cpp_smoke_workspace",
                "gui_headless_smoke",
                "runtime_contract",
                "win7_cli_smoke",
                "win7_windowed_gui_smoke",
            ]
            if gui
            else ["runtime_contract", "win7_cli_smoke"]
        ),
    }
    path.write_text(json.dumps(plan, sort_keys=True), encoding="ascii")
    return path, plan


def test_canonical_json_is_sorted_compact_and_ascii_safe():
    module = _load_module()

    value = {"z": "cafe", "a": {"two": 2, "one": 1}}
    encoded = module.canonical_json(value)

    assert encoded == '{"a":{"one":1,"two":2},"z":"cafe"}'
    assert json.loads(encoded) == value


def test_tree_hash_is_stable_and_changes_when_a_file_changes(tmp_path):
    module = _load_module()
    root = tmp_path / "static"
    (root / "nested").mkdir(parents=True)
    (root / "z.txt").write_text("z", encoding="ascii")
    (root / "nested" / "a.txt").write_text("a", encoding="ascii")

    first = module.sha256_tree(root)
    second = module.sha256_tree(root)
    assert first == second

    (root / "nested" / "a.txt").write_text("changed", encoding="ascii")
    assert module.sha256_tree(root) != first


def test_release_identity_contains_exact_six_wheels_without_operational_timestamps(tmp_path):
    module = _load_module()
    wheels = _wheels(tmp_path)
    static_root = tmp_path / "static"
    static_root.mkdir()
    (static_root / "app.js").write_text("app", encoding="ascii")
    asset_manifest = tmp_path / "offline-assets.json"
    asset_manifest.write_text('{"schema_version": 1}', encoding="ascii")
    runtime_contract = tmp_path / "offline-runtime-contract.json"
    runtime_contract.write_text('{"schema_version": 1}', encoding="ascii")
    bundle_plan, plan = _bundle_plan(tmp_path)

    identity = module.build_release_identity(
        source_revision="abc123",
        version="0.1.0",
        profile="release",
        wheels=wheels,
        gui_static_root=static_root,
        asset_manifest_path=asset_manifest,
        runtime_contract_path=runtime_contract,
        bundle_plan_path=bundle_plan,
        tool_metadata={"python": "3.8.10"},
    )

    assert identity["schema_version"] == 2
    assert identity["flavor_id"] == "minimal-cli"
    assert identity["target_id"] == "win7-x64-portable"
    assert identity["bundle_plan_sha256"] == module.sha256_file(bundle_plan)
    assert identity["agent_lock_sha256"] == plan["agent_lock_sha256"]
    assert identity["gate_ids"] == ["runtime_contract", "win7_cli_smoke"]
    assert identity["gui_static_sha256"] is None
    assert identity["project_distributions"] == [
        "embedagent-core",
        "embedagent-protocol",
        "embedagent-host",
        "embedagent-composition",
        "embedagent-workflow-cpp",
        "embedagent",
    ]
    assert [item["name"] for item in identity["wheels"]] == identity["project_distributions"]
    assert "started_at" not in identity
    assert "timestamp" not in json.dumps(identity)
    assert module.compare_release_identity(identity, dict(identity))["ok"]


def test_release_identity_rejects_duplicate_or_sensitive_inputs(tmp_path):
    module = _load_module()
    wheels = _wheels(tmp_path)
    bundle_plan, _ = _bundle_plan(tmp_path)
    with pytest.raises(ValueError, match="duplicate"):
        module.build_release_identity(
            source_revision="abc",
            version="0.1.0",
            profile="release",
            wheels=wheels + [wheels[0]],
            gui_static_root=tmp_path,
            asset_manifest_path=tmp_path / "asset.json",
            runtime_contract_path=tmp_path / "contract.json",
            bundle_plan_path=bundle_plan,
        )

    with pytest.raises(ValueError, match="sensitive"):
        module.build_release_identity(
            source_revision="abc",
            version="0.1.0",
            profile="release",
            wheels=wheels,
            gui_static_root=tmp_path,
            asset_manifest_path=tmp_path / "asset.json",
            runtime_contract_path=tmp_path / "contract.json",
            bundle_plan_path=bundle_plan,
            tool_metadata={"api_key": "secret"},
        )


def test_identity_comparison_reports_nested_mismatches(tmp_path):
    module = _load_module()
    wheels = _wheels(tmp_path)
    bundle_plan, _ = _bundle_plan(tmp_path)
    identity = module.build_release_identity(
        source_revision="abc",
        version="0.1.0",
        profile="release",
        wheels=wheels,
        gui_static_root=tmp_path,
        asset_manifest_path=wheels[0][1],
        runtime_contract_path=wheels[1][1],
        bundle_plan_path=bundle_plan,
    )
    mutations = {
        "profile": "dev",
        "flavor_id": "cpp-desktop",
        "target_id": "other-target",
        "bundle_plan_sha256": "e" * 64,
        "agent_lock_sha256": "d" * 64,
        "gate_ids": ["runtime_contract"],
    }

    for field, value in mutations.items():
        changed = copy.deepcopy(identity)
        changed[field] = value
        result = module.compare_release_identity(identity, changed)
        assert not result["ok"]
        assert field in result["mismatches"]


def test_release_identity_requires_gui_static_only_for_gui_plan(tmp_path):
    module = _load_module()
    wheels = _wheels(tmp_path)
    bundle_plan, _ = _bundle_plan(tmp_path, flavor_id="cpp-desktop", gui=True)

    with pytest.raises(ValueError, match="GUI static root"):
        module.build_release_identity(
            source_revision="abc",
            version="0.1.0",
            profile="release",
            wheels=wheels,
            gui_static_root=None,
            asset_manifest_path=wheels[0][1],
            runtime_contract_path=wheels[1][1],
            bundle_plan_path=bundle_plan,
        )


def test_identity_cli_allows_minimal_plan_without_gui_static_root(tmp_path):
    wheel_dir = tmp_path / "wheels"
    wheel_dir.mkdir()
    _wheels(wheel_dir)
    bundle_plan, _ = _bundle_plan(tmp_path)
    asset_manifest = tmp_path / "assets.json"
    runtime_contract = tmp_path / "runtime-contract.json"
    asset_manifest.write_text("{}", encoding="ascii")
    runtime_contract.write_text("{}", encoding="ascii")
    output = tmp_path / "release-identity.json"

    result = subprocess.run(
        [
            sys.executable,
            str(CREATE_SCRIPT),
            "--project-root",
            str(ROOT),
            "--profile",
            "release",
            "--wheel-dir",
            str(wheel_dir),
            "--bundle-plan",
            str(bundle_plan),
            "--asset-manifest",
            str(asset_manifest),
            "--runtime-contract",
            str(runtime_contract),
            "--output",
            str(output),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text(encoding="ascii"))["gui_static_sha256"] is None
