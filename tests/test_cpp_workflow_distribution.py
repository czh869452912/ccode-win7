import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "embedagent-workflow-cpp" / "src" / "embedagent_workflow_cpp"
FORBIDDEN_IMPORTS = (
    "embedagent",
    "embedagent_composition",
    "embedagent_host",
    "embedagent_protocol",
)


DEFERRED_RESOURCE_IMPORTS = {
    "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/workspace_recipes.py": (
        "embedagent_host.runtime.local_resources",
    ),
}


def _imported_modules(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            yield node.module or ""
        elif isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name


def _cpp_imports():
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative_path = path.relative_to(ROOT).as_posix()
        for module in _imported_modules(tree):
            yield relative_path, module


def test_cpp_workflow_package_exists():
    assert (PACKAGE / "__init__.py").is_file()
    assert (PACKAGE / "component.py").is_file()


def test_cpp_workflow_does_not_import_forbidden_workspace_packages():
    offenders = []
    deferred = {
        (relative_path, module)
        for relative_path, modules in DEFERRED_RESOURCE_IMPORTS.items()
        for module in modules
    }
    for relative_path, module in _cpp_imports():
        if (relative_path, module) in deferred:
            continue
        if any(module == name or module.startswith(name + ".") for name in FORBIDDEN_IMPORTS):
            offenders.append((relative_path, module))
    assert offenders == []


def test_legacy_nested_cpp_package_is_deleted():
    assert not (ROOT / "src" / "embedagent" / "workflow_packages" / "c_cpp").exists()


def test_cpp_workflow_deferred_imports_are_resource_only():
    expected = sorted(
        (relative_path, module)
        for relative_path, modules in DEFERRED_RESOURCE_IMPORTS.items()
        for module in modules
    )
    actual = sorted(
        (relative_path, module)
        for relative_path, module in _cpp_imports()
        if (relative_path, module) in expected
    )
    assert actual == expected


def test_cpp_component_returns_core_runtime_definition():
    from embedagent_core import RuntimeDefinition
    from embedagent_workflow_cpp import cpp_runtime_definition

    definition = cpp_runtime_definition()
    assert isinstance(definition, RuntimeDefinition)
    assert definition.agent_id == "embedagent.default_c_cpp"
    assert len(definition.extensions) == 1
    assert definition.workflow_state == ""


def test_cpp_package_root_exports_only_contracts():
    import embedagent_workflow_cpp as package

    assert package.__all__ == ["C_WORKFLOW_PACKAGE_ID", "cpp_runtime_definition"]
    assert not hasattr(package, "default_c_cpp_agent_profile")
    assert not hasattr(package, "build_c_cpp_agent_application")
