from __future__ import annotations

from embedagent_composition import (
    AgentProductDefinition,
    ComponentCatalog,
    ComponentManifest,
    ComponentRef,
    FrozenBundleRecipeRegistry,
    FrozenComponentCatalog,
    OfficialBundleRecipe,
)

_VERSION = "0.1.0"
_API_VERSION = "agent_component_v1"


def _manifest(
    component_id,
    kind,
    distribution_id,
    requires=(),
    runtime_requirements=(),
    registration_entry="",
):
    return ComponentManifest(
        component_id=component_id,
        kind=kind,
        version=_VERSION,
        api_version=_API_VERSION,
        distribution_id=distribution_id,
        registration_entry=registration_entry,
        requires=tuple(requires),
        runtime_requirements=tuple(runtime_requirements),
    )


def product_component_catalog() -> FrozenComponentCatalog:
    catalog = ComponentCatalog()
    manifests = (
        _manifest("embedagent-core", "distribution", "embedagent-core"),
        _manifest("embedagent-protocol", "distribution", "embedagent-protocol"),
        _manifest(
            "embedagent-host",
            "distribution",
            "embedagent-host",
            requires=("embedagent-core", "embedagent-protocol"),
        ),
        _manifest("embedagent-composition", "distribution", "embedagent-composition"),
        _manifest(
            "embedagent-workflow-cpp",
            "distribution",
            "embedagent-workflow-cpp",
            requires=("embedagent-core",),
        ),
        _manifest(
            "embedagent-shell",
            "distribution",
            "embedagent-shell",
            requires=(
                "embedagent-core",
                "embedagent-protocol",
                "embedagent-host",
            ),
            registration_entry="embedagent.product_catalog:register",
        ),
        _manifest(
            "profile.generic",
            "profile",
            "embedagent-shell",
            requires=("embedagent-core",),
            runtime_requirements=("runtime.python",),
        ),
        _manifest(
            "profile.cpp",
            "profile",
            "embedagent-workflow-cpp",
            requires=("embedagent-core",),
            runtime_requirements=("runtime.python",),
            registration_entry="embedagent_workflow_cpp.application:register",
        ),
        _manifest(
            "provider.openai-compatible",
            "provider",
            "embedagent-host",
            requires=("embedagent-host",),
            runtime_requirements=("runtime.python",),
        ),
        _manifest(
            "toolset.workflow-neutral",
            "toolset",
            "embedagent-host",
            requires=("embedagent-host",),
            runtime_requirements=(
                "runtime.python",
                "vcs.git",
                "shell.bash",
                "search.rg",
            ),
        ),
        _manifest(
            "workflow.cpp",
            "workflow",
            "embedagent-workflow-cpp",
            requires=("embedagent-workflow-cpp",),
            runtime_requirements=("toolchain.clang", "symbols.ctags"),
            registration_entry="embedagent_workflow_cpp.application:register",
        ),
        _manifest("shell.cli", "shell", "embedagent-shell", requires=("embedagent-shell",)),
        _manifest(
            "shell.tui",
            "shell",
            "embedagent-shell",
            requires=("embedagent-shell",),
            runtime_requirements=("python-feature.tui",),
        ),
        _manifest(
            "shell.gui",
            "shell",
            "embedagent-shell",
            requires=("embedagent-shell",),
            runtime_requirements=("python-feature.gui", "renderer.webview2"),
        ),
    )
    for manifest in manifests:
        catalog.register(manifest)
    return catalog.freeze()


def _minimal_cli_definition() -> AgentProductDefinition:
    return AgentProductDefinition(
        agent_id="embedagent.generic",
        profile=ComponentRef("profile.generic"),
        providers=(ComponentRef("provider.openai-compatible"),),
        tools=(ComponentRef("toolset.workflow-neutral"),),
        host=ComponentRef("embedagent-host"),
        shells=(ComponentRef("shell.cli"),),
    )


def _cpp_desktop_definition() -> AgentProductDefinition:
    return AgentProductDefinition(
        agent_id="embedagent.default_c_cpp",
        profile=ComponentRef("profile.cpp"),
        providers=(ComponentRef("provider.openai-compatible"),),
        workflows=(ComponentRef("workflow.cpp"),),
        tools=(ComponentRef("toolset.workflow-neutral"),),
        host=ComponentRef("embedagent-host"),
        shells=(
            ComponentRef("shell.cli"),
            ComponentRef("shell.tui"),
            ComponentRef("shell.gui"),
        ),
    )


def official_bundle_recipe_registry() -> FrozenBundleRecipeRegistry:
    return FrozenBundleRecipeRegistry(
        (
            OfficialBundleRecipe(
                recipe_id="minimal-cli",
                definition_factory=_minimal_cli_definition,
                shell_ids=("cli",),
                config_template_id="minimal-cli",
            ),
            OfficialBundleRecipe(
                recipe_id="cpp-desktop",
                definition_factory=_cpp_desktop_definition,
                shell_ids=("cli", "tui", "gui"),
                config_template_id="cpp-desktop",
            ),
        )
    )
