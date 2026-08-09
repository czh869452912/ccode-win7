from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Tuple

from .errors import CompositionError
from .model import AgentProductDefinition


@dataclass(frozen=True)
class OfficialBundleRecipe:
    recipe_id: str
    definition_factory: Callable[[], AgentProductDefinition]
    shell_ids: Tuple[str, ...]
    config_template_id: str

    def __post_init__(self) -> None:
        recipe_id = str(self.recipe_id or "").strip()
        template_id = str(self.config_template_id or "").strip()
        shells = tuple(str(item or "").strip() for item in self.shell_ids)
        if not recipe_id or not template_id or not callable(self.definition_factory):
            raise CompositionError("invalid_bundle_recipe", recipe_id)
        if not shells or any(not item for item in shells) or len(set(shells)) != len(shells):
            raise CompositionError("invalid_bundle_recipe_shells", recipe_id)
        object.__setattr__(self, "recipe_id", recipe_id)
        object.__setattr__(self, "config_template_id", template_id)
        object.__setattr__(self, "shell_ids", shells)


class FrozenBundleRecipeRegistry(object):
    def __init__(self, recipes: Iterable[OfficialBundleRecipe]):
        records = {}  # type: Dict[str, OfficialBundleRecipe]
        for recipe in recipes:
            if recipe.recipe_id in records:
                raise CompositionError("duplicate_bundle_recipe", recipe.recipe_id)
            records[recipe.recipe_id] = recipe
        if not records:
            raise CompositionError("empty_bundle_recipe_registry", "no recipes registered")
        self._recipes = records

    def names(self) -> Tuple[str, ...]:
        return tuple(sorted(self._recipes))

    def resolve(self, recipe_id: str) -> OfficialBundleRecipe:
        requested = str(recipe_id or "").strip()
        try:
            return self._recipes[requested]
        except KeyError:
            raise CompositionError("unknown_bundle_recipe", requested)
