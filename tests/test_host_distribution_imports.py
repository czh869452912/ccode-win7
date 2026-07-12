import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST_ROOT = ROOT / "packages" / "embedagent-host" / "src" / "embedagent_host"


def _host_import_offenders():
    offenders = []
    for path in HOST_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = ""
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "embedagent" or alias.name.startswith("embedagent."):
                        offenders.append((str(path.relative_to(ROOT)), alias.name))
            if module == "embedagent" or module.startswith("embedagent."):
                offenders.append((str(path.relative_to(ROOT)), module))
            if "workflow_packages.c_cpp" in module:
                offenders.append((str(path.relative_to(ROOT)), module))
    return sorted(set(offenders))


def test_host_has_exclusive_physical_ownership():
    assert HOST_ROOT.is_dir()
    assert (HOST_ROOT / "runtime" / "tools" / "runtime.py").is_file()
    assert (HOST_ROOT / "runtime" / "services" / "session_lifecycle.py").is_file()
    assert not (ROOT / "src" / "embedagent_host").exists()


def test_host_does_not_import_product_or_default_workflow():
    assert _host_import_offenders() == []


def test_host_imports_with_only_core_and_protocol_distributions_visible():
    package_roots = [
        ROOT / "packages" / "embedagent-host" / "src",
        ROOT / "packages" / "embedagent-core" / "src",
        ROOT / "packages" / "embedagent-protocol" / "src",
    ]
    script = (
        "import pkgutil, sys\n"
        "roots = %r\n"
        "sys.path[:] = roots + [item for item in sys.path "
        "if item and 'site-packages' not in item and item not in roots]\n"
        "import embedagent_host\n"
        "names = [item.name for item in "
        "pkgutil.walk_packages(embedagent_host.__path__, embedagent_host.__name__ + '.')]\n"
        "for name in names:\n"
        "    __import__(name)\n"
        "blocked = [name for name in sys.modules "
        "if name == 'embedagent' or name.startswith('embedagent.')]\n"
        "raise SystemExit('product modules loaded: %%r' %% blocked if blocked else 0)\n"
    ) % [str(path) for path in package_roots]
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
