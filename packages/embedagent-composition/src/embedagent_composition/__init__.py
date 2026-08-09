"""Dependency-free build-time Agent composition and export contracts."""

from .compiler import compile_agent
from .errors import CompositionError
from .export import export_agent
from .model import (
    AgentProductDefinition,
    CompiledAgentSpec,
    ComponentManifest,
    ComponentRef,
)
from .recipes import FrozenBundleRecipeRegistry, OfficialBundleRecipe

__version__ = "0.1.0"

__all__ = [
    "AgentProductDefinition",
    "CompiledAgentSpec",
    "ComponentManifest",
    "ComponentRef",
    "CompositionError",
    "FrozenBundleRecipeRegistry",
    "OfficialBundleRecipe",
    "compile_agent",
    "export_agent",
]
