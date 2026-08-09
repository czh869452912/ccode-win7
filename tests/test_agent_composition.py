import json

import pytest
from embedagent_composition.catalog import ComponentCatalog
from embedagent_composition.compiler import compile_agent
from embedagent_composition.errors import CompositionError
from embedagent_composition.export import export_agent
from embedagent_composition.model import AgentProductDefinition, ComponentManifest, ComponentRef


def manifest(
    component_id,
    kind,
    requires=(),
    conflicts=(),
    assets=(),
    namespaces=(),
    runtime_requirements=(),
):
    return ComponentManifest(
        component_id=component_id,
        kind=kind,
        version="0.1.0",
        api_version="agent_component_v1",
        requires=tuple(requires),
        conflicts=tuple(conflicts),
        runtime_assets=tuple(assets),
        namespaces=tuple(namespaces),
        runtime_requirements=tuple(runtime_requirements),
    )


def make_catalog():
    catalog = ComponentCatalog()
    catalog.register(manifest("embedagent-core", "runtime", assets=("core.txt",)))
    catalog.register(
        manifest(
            "embedagent-protocol",
            "protocol",
            requires=("embedagent-core",),
            assets=("protocol.txt",),
        )
    )
    catalog.register(
        manifest(
            "embedagent-host",
            "host",
            requires=("embedagent-core", "embedagent-protocol"),
            assets=("host.txt",),
        )
    )
    catalog.register(manifest("embedagent-composition", "composition"))
    catalog.register(
        manifest(
            "embedagent-workflow-cpp",
            "workflow",
            requires=("embedagent-core",),
            assets=("cpp.txt",),
            namespaces=("workflow:cpp", "tool:run_recipe"),
        )
    )
    catalog.register(manifest("embedagent-generic", "profile", requires=("embedagent-core",)))
    return catalog.freeze()


def base_definition():
    return AgentProductDefinition(
        agent_id="embedagent.generic",
        profile=ComponentRef("embedagent-generic"),
        providers=(ComponentRef("embedagent-protocol"),),
        tools=(ComponentRef("embedagent-composition"),),
        host=ComponentRef("embedagent-host"),
    )


def cpp_definition():
    return AgentProductDefinition(
        agent_id="embedagent.default_c_cpp",
        profile=ComponentRef("embedagent-generic"),
        providers=(ComponentRef("embedagent-protocol"),),
        workflows=(ComponentRef("embedagent-workflow-cpp"),),
        tools=(ComponentRef("embedagent-composition"),),
        host=ComponentRef("embedagent-host"),
    )


def test_compile_is_deterministic_and_base_has_no_cpp_workflow():
    catalog = make_catalog()
    first = compile_agent(base_definition(), catalog)
    second = compile_agent(base_definition(), catalog)
    assert first.to_dict() == second.to_dict()
    component_ids = [item["component_id"] for item in first.manifest["components"]]
    assert "embedagent-workflow-cpp" not in component_ids
    assert component_ids.index("embedagent-core") < component_ids.index("embedagent-host")
    assert component_ids.index("embedagent-protocol") < component_ids.index("embedagent-host")


def test_cpp_export_contains_workflow_assets_and_reproducible_lock(tmp_path):
    catalog = make_catalog()
    asset_root = tmp_path / "assets"
    asset_root.mkdir()
    for name in ("core.txt", "protocol.txt", "host.txt", "cpp.txt"):
        (asset_root / name).write_text(name, encoding="ascii")
    wheel_root = tmp_path / "wheels"
    wheel_root.mkdir()
    wheel = wheel_root / "embedagent-workflow-cpp-0.1.0.whl"
    wheel.write_bytes(b"workflow-wheel")

    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first = export_agent(
        cpp_definition(),
        catalog,
        first_dir,
        asset_root=asset_root,
        component_files={"embedagent-workflow-cpp": wheel},
    )
    second = export_agent(
        cpp_definition(),
        catalog,
        second_dir,
        asset_root=asset_root,
        component_files={"embedagent-workflow-cpp": wheel},
    )

    assert (first_dir / "agent.json").is_file()
    assert (first_dir / "agent.lock.json").is_file()
    assert (first_dir / "export-report.json").is_file()
    assert (first_dir / "components" / wheel.name).read_bytes() == b"workflow-wheel"
    assert first.to_dict() == second.to_dict()
    assert (first_dir / "agent.lock.json").read_bytes() == (
        second_dir / "agent.lock.json"
    ).read_bytes()
    lock = json.loads((first_dir / "agent.lock.json").read_text(encoding="utf-8"))
    assert any(item["component_id"] == "embedagent-workflow-cpp" for item in lock["components"])
    assert "api_key" not in (first_dir / "export-report.json").read_text(encoding="utf-8")


def test_catalog_rejects_duplicate_namespace_and_asset_escape():
    catalog = ComponentCatalog()
    catalog.register(manifest("one", "tool", namespaces=("tool:duplicate",)))
    catalog.register(manifest("two", "tool", namespaces=("tool:duplicate",)))
    with pytest.raises(CompositionError) as duplicate:
        catalog.freeze()
    assert duplicate.value.code == "duplicate_namespace"

    safe = ComponentCatalog()
    with pytest.raises(CompositionError) as escape:
        safe.register(manifest("safe", "profile", assets=("../escape.txt",)))
    assert escape.value.code == "unsafe_asset_path"


def test_shells_and_runtime_requirements_are_compiled_deterministically():
    catalog = ComponentCatalog()
    catalog.register(manifest("profile", "profile"))
    catalog.register(
        manifest(
            "shell.cli",
            "shell",
            runtime_requirements=("runtime.python", "search.rg"),
        )
    )
    definition = AgentProductDefinition(
        agent_id="tests.agent",
        profile=ComponentRef("profile"),
        shells=(ComponentRef("shell.cli"),),
    )

    compiled = compile_agent(definition, catalog.freeze())

    shell_ids = tuple(ref.component_id for ref in definition.component_refs())
    assert shell_ids.count("shell.cli") == 1
    components = dict(
        (item["component_id"], item) for item in compiled.manifest["components"]
    )
    assert components["shell.cli"]["runtime_requirements"] == [
        "runtime.python",
        "search.rg",
    ]


@pytest.mark.parametrize(
    "requirement",
    ("", "Runtime.Python", "runtime python", "runtime/python", "runtime..python"),
)
def test_catalog_rejects_invalid_runtime_requirement(requirement):
    catalog = ComponentCatalog()
    with pytest.raises(CompositionError) as error:
        catalog.register(
            manifest(
                "invalid",
                "profile",
                runtime_requirements=(requirement,),
            )
        )
    assert error.value.code == "invalid_runtime_requirement"
