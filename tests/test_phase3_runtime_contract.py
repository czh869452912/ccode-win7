import hashlib
import json

import pytest

from embedagent.bundle_policy import load_bundle_policy


def _bundle_with_closure(tmp_path, **overrides):
    root = tmp_path
    manifests = root / "manifests"
    manifests.mkdir()
    plan = {
        "schema_version": 1,
        "flavor_id": "cpp-desktop",
        "allowed_agent_application_ids": ["embedagent.cpp"],
        "shell_ids": ["cli", "gui"],
        "registration_entries": ["embedagent.product_catalog:register"],
        "runtime_capability_ids": ["runtime.python", "runtime.clang"],
        "runtime_component_ids": ["runtime.python38", "runtime.llvm"],
        "asset_ids": ["asset.python38", "asset.clang"],
        "gate_ids": ["gate.cli", "gate.cpp"],
        "project_distribution_ids": [
            "embedagent-core",
            "embedagent-protocol",
            "embedagent-host",
            "embedagent-workflow-cpp",
            "embedagent-shell",
        ],
    }
    plan.update(overrides)
    plan_path = manifests / "bundle-plan.json"
    plan_path.write_text(json.dumps(plan, sort_keys=True), encoding="ascii")
    plan_hash = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    (manifests / "bundle-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "flavor_id": "cpp-desktop",
                "bundle_plan_sha256": plan_hash,
            }
        ),
        encoding="ascii",
    )
    return root


def test_bundle_policy_projects_selected_runtime_closure_as_tuples(tmp_path):
    policy = load_bundle_policy(str(_bundle_with_closure(tmp_path)))

    assert policy.runtime_capability_ids == ("runtime.python", "runtime.clang")
    assert policy.runtime_component_ids == ("runtime.python38", "runtime.llvm")
    assert policy.asset_ids == ("asset.python38", "asset.clang")
    assert policy.gate_ids == ("gate.cli", "gate.cpp")
    assert policy.project_distribution_ids == (
        "embedagent-core",
        "embedagent-protocol",
        "embedagent-host",
        "embedagent-workflow-cpp",
        "embedagent-shell",
    )


@pytest.mark.parametrize(
    "field_name",
    [
        "runtime_capability_ids",
        "runtime_component_ids",
        "asset_ids",
        "gate_ids",
        "project_distribution_ids",
    ],
)
def test_bundle_policy_rejects_duplicate_selected_closure_ids(tmp_path, field_name):
    with pytest.raises(ValueError, match="unique nonempty ids"):
        load_bundle_policy(
            str(
                _bundle_with_closure(
                    tmp_path,
                    **{field_name: ["duplicate", "duplicate"]},
                )
            )
        )


def test_bundle_policy_rejects_malformed_registration_entry(tmp_path):
    with pytest.raises(ValueError, match="registration_entries"):
        load_bundle_policy(
            str(
                _bundle_with_closure(
                    tmp_path,
                    registration_entries=["embedagent.product_catalog"],
                )
            )
        )
