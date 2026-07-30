import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_identity.py"


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

    identity = module.build_release_identity(
        source_revision="abc123",
        version="0.1.0",
        profile="release",
        wheels=wheels,
        gui_static_root=static_root,
        asset_manifest_path=asset_manifest,
        runtime_contract_path=runtime_contract,
        tool_metadata={"python": "3.8.10"},
    )

    assert identity["schema_version"] == 1
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
    with pytest.raises(ValueError, match="duplicate"):
        module.build_release_identity(
            source_revision="abc",
            version="0.1.0",
            profile="release",
            wheels=wheels + [wheels[0]],
            gui_static_root=tmp_path,
            asset_manifest_path=tmp_path / "asset.json",
            runtime_contract_path=tmp_path / "contract.json",
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
            tool_metadata={"api_key": "secret"},
        )


def test_identity_comparison_reports_nested_mismatches(tmp_path):
    module = _load_module()
    wheels = _wheels(tmp_path)
    identity = module.build_release_identity(
        source_revision="abc",
        version="0.1.0",
        profile="release",
        wheels=wheels,
        gui_static_root=tmp_path,
        asset_manifest_path=wheels[0][1],
        runtime_contract_path=wheels[1][1],
    )
    changed = dict(identity)
    changed["profile"] = "dev"

    result = module.compare_release_identity(identity, changed)

    assert not result["ok"]
    assert "profile" in result["mismatches"]
