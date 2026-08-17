import hashlib
import json

import pytest
from embedagent_composition import (
    AgentProductDefinition,
    ComponentCatalog,
    ComponentManifest,
    ComponentRef,
    CompositionError,
    FrozenBundleRecipeRegistry,
    OfficialBundleRecipe,
    compile_bundle_plan,
)


def _definition():
    return AgentProductDefinition(
        agent_id="tests.generic",
        profile=ComponentRef("profile.generic"),
        shells=(ComponentRef("shell.cli"),),
    )


def _recipe(recipe_id="minimal-cli"):
    return OfficialBundleRecipe(
        recipe_id=recipe_id,
        definition_factory=_definition,
        shell_ids=("cli",),
        config_template_id="minimal-cli",
    )


def _catalog():
    catalog = ComponentCatalog()
    catalog.register(
        ComponentManifest(
            component_id="embedagent-core",
            kind="distribution",
            version="0.1.0",
            api_version="agent_component_v1",
            distribution_id="embedagent-core",
        )
    )
    catalog.register(
        ComponentManifest(
            component_id="profile.generic",
            kind="profile",
            version="0.1.0",
            api_version="agent_component_v1",
            distribution_id="embedagent-core",
            runtime_requirements=("runtime.python",),
        )
    )
    catalog.register(
        ComponentManifest(
            component_id="shell.cli",
            kind="shell",
            version="0.1.0",
            api_version="agent_component_v1",
            distribution_id="embedagent-core",
        )
    )
    return catalog.freeze()


def _runtime_contract():
    return {
        "schema_version": 2,
        "targets": {
            "win7-x64-portable": {
                "always_requires": ["runtime.python"],
                "always_gates": ["runtime_contract"],
            }
        },
        "runtime_components": [
            {
                "id": "python",
                "provides": ["runtime.python"],
                "asset_ids": ["python_embedded_x64"],
                "paths": ["runtime/python/python.exe"],
                "python_feature_ids": [],
                "launcher_ids": ["cli"],
            }
        ],
        "launchers": [{"id": "cli", "path": "embedagent.cmd"}],
        "release_gates": [{"id": "runtime_contract", "applies_when": {"all_of": []}}],
    }


def _asset_manifest():
    return {
        "schema_version": 1,
        "assets": [
            {
                "id": "python_embedded_x64",
                "version": "3.8.10",
                "sha256": "a" * 64,
            }
        ],
    }


def test_recipe_registry_is_sorted_and_frozen():
    registry = FrozenBundleRecipeRegistry((_recipe("z-last"), _recipe("a-first")))
    assert registry.names() == ("a-first", "z-last")
    assert registry.resolve("a-first").definition_factory().agent_id == "tests.generic"


def test_recipe_registry_rejects_duplicates_and_unknown_ids():
    with pytest.raises(CompositionError) as duplicate:
        FrozenBundleRecipeRegistry((_recipe(), _recipe()))
    assert duplicate.value.code == "duplicate_bundle_recipe"

    registry = FrozenBundleRecipeRegistry((_recipe(),))
    with pytest.raises(CompositionError) as unknown:
        registry.resolve("missing")
    assert unknown.value.code == "unknown_bundle_recipe"


def test_bundle_plan_is_deterministic_and_projects_selected_distributions():
    first = compile_bundle_plan(
        recipe=_recipe(),
        catalog=_catalog(),
        runtime_contract=_runtime_contract(),
        asset_manifest=_asset_manifest(),
        target_id="win7-x64-portable",
        assurance="release",
    )
    second = compile_bundle_plan(
        recipe=_recipe(),
        catalog=_catalog(),
        runtime_contract=_runtime_contract(),
        asset_manifest=_asset_manifest(),
        target_id="win7-x64-portable",
        assurance="release",
    )

    assert first.to_dict() == second.to_dict()
    assert first.project_distribution_ids == ("embedagent-core",)
    assert first.config_template_id == "minimal-cli"
    assert first.allowed_agent_application_ids == ("tests.generic",)
    assert first.runtime_capability_ids == ("runtime.python",)
    assert first.asset_ids == ("python_embedded_x64",)
    assert first.launcher_ids == ("cli",)
    assert first.gate_ids == ("runtime_contract",)
    encoded = json.dumps(first.to_dict(), sort_keys=True, separators=(",", ":"))
    assert first.sha256 == hashlib.sha256(encoded.encode("ascii")).hexdigest()


def test_bundle_plan_rejects_ambiguous_runtime_provider():
    contract = _runtime_contract()
    contract["runtime_components"].append(
        {
            "id": "second-python",
            "provides": ["runtime.python"],
            "asset_ids": [],
            "paths": ["runtime/python/other.exe"],
            "python_feature_ids": [],
            "launcher_ids": [],
        }
    )
    with pytest.raises(CompositionError) as error:
        compile_bundle_plan(
            recipe=_recipe(),
            catalog=_catalog(),
            runtime_contract=contract,
            asset_manifest=_asset_manifest(),
            target_id="win7-x64-portable",
            assurance="release",
        )
    assert error.value.code == "ambiguous_runtime_provider"


def test_bundle_plan_rejects_unknown_condition_fact():
    contract = _runtime_contract()
    contract["release_gates"].append(
        {
            "id": "unknown-fact",
            "applies_when": {"all_of": ["recipe.untrusted"]},
        }
    )

    with pytest.raises(CompositionError) as error:
        compile_bundle_plan(
            recipe=_recipe(),
            catalog=_catalog(),
            runtime_contract=contract,
            asset_manifest=_asset_manifest(),
            target_id="win7-x64-portable",
            assurance="release",
        )
    assert error.value.code == "unknown_bundle_fact"


def test_bundle_plan_rejects_runtime_dependency_cycles():
    contract = _runtime_contract()
    contract["runtime_components"][0]["requires"] = ["runtime.loop"]
    contract["runtime_components"].append(
        {
            "id": "loop",
            "provides": ["runtime.loop"],
            "requires": ["runtime.python"],
            "asset_ids": [],
            "paths": [],
            "python_feature_ids": [],
            "launcher_ids": [],
        }
    )

    with pytest.raises(CompositionError) as error:
        compile_bundle_plan(
            recipe=_recipe(),
            catalog=_catalog(),
            runtime_contract=contract,
            asset_manifest=_asset_manifest(),
            target_id="win7-x64-portable",
            assurance="release",
        )
    assert error.value.code == "runtime_component_cycle"


def test_bundle_plan_rejects_unregistered_launcher():
    contract = _runtime_contract()
    contract["launchers"] = []

    with pytest.raises(CompositionError) as error:
        compile_bundle_plan(
            recipe=_recipe(),
            catalog=_catalog(),
            runtime_contract=contract,
            asset_manifest=_asset_manifest(),
            target_id="win7-x64-portable",
            assurance="release",
        )
    assert error.value.code == "unknown_bundle_launcher"
