"""Dependency-free build-time Agent composition and export contracts."""

from .bundle import PORTABLE_PROJECT_DISTRIBUTIONS, CompiledBundlePlan, compile_bundle_plan
from .catalog import ComponentCatalog, FrozenComponentCatalog
from .compiler import compile_agent
from .errors import CompositionError
from .export import export_agent
from .application import ApplicationManifest, DistributionManifest, validate_application_manifest
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
    "ApplicationManifest",
    "CompiledBundlePlan",
    "CompiledAgentSpec",
    "ComponentCatalog",
    "ComponentManifest",
    "ComponentRef",
    "CompositionError",
    "DistributionManifest",
    "FrozenBundleRecipeRegistry",
    "FrozenComponentCatalog",
    "OfficialBundleRecipe",
    "PORTABLE_PROJECT_DISTRIBUTIONS",
    "compile_agent",
    "compile_bundle_plan",
    "export_agent",
    "validate_application_manifest",
]
