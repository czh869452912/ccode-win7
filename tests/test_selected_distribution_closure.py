from __future__ import annotations

import json
from pathlib import Path

from embedagent_composition import compile_bundle_plan

from embedagent.bundle_catalog import official_bundle_recipe_registry, product_component_catalog

ROOT = Path(__file__).resolve().parents[1]


def compile_bundle_plan_for(flavor, target_id="win7-x64-portable", assurance="dev"):
    recipe = official_bundle_recipe_registry().resolve(flavor)
    return compile_bundle_plan(
        recipe=recipe,
        catalog=product_component_catalog(),
        runtime_contract=json.loads(
            (ROOT / "scripts" / "offline-runtime-contract.json").read_text(encoding="utf-8")
        ),
        asset_manifest=json.loads(
            (ROOT / "scripts" / "offline-assets.json").read_text(encoding="utf-8")
        ),
        target_id=target_id,
        assurance=assurance,
    )


def test_minimal_plan_contains_no_cpp_distribution_or_composition_runtime():
    plan = compile_bundle_plan_for("minimal-cli")
    assert "embedagent-workflow-cpp" not in plan.project_distribution_ids
    assert "embedagent-shell" in plan.project_distribution_ids
    assert "embedagent-composition" not in plan.project_distribution_ids


def test_cpp_plan_adds_only_selected_workflow_distribution_and_assets():
    plan = compile_bundle_plan_for("cpp-desktop")
    assert "embedagent-workflow-cpp" in plan.project_distribution_ids
    assert "toolchain.clang" in plan.runtime_capability_ids
    assert "symbols.ctags" in plan.runtime_capability_ids


def test_distribution_owner_is_derived_from_selected_components():
    plan = compile_bundle_plan_for("minimal-cli")
    catalog = product_component_catalog()
    owners = {
        getattr(catalog.manifest(component_id), "distribution_id", None)
        for component_id in plan.component_ids
    }
    assert None not in owners
    assert set(plan.project_distribution_ids) == owners
