import pytest
from embedagent_composition import (
    AgentProductDefinition,
    ComponentRef,
    CompositionError,
    FrozenBundleRecipeRegistry,
    OfficialBundleRecipe,
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
