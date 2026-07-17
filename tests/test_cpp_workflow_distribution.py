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


def _imported_modules(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            yield node.module or ""
        elif isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name


def test_cpp_workflow_package_exists():
    assert (PACKAGE / "__init__.py").is_file()
    assert (PACKAGE / "component.py").is_file()


def test_cpp_workflow_does_not_import_forbidden_workspace_packages():
    offenders = []
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module in _imported_modules(tree):
            if any(module == name or module.startswith(name + ".") for name in FORBIDDEN_IMPORTS):
                offenders.append((str(path.relative_to(ROOT)), module))
    assert offenders == []


def test_legacy_nested_cpp_package_is_deleted():
    assert not (ROOT / "src" / "embedagent" / "workflow_packages" / "c_cpp").exists()
