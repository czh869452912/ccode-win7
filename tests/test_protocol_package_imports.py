import ast
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
PROTOCOL_SOURCE = os.path.join(
    ROOT,
    "packages",
    "embedagent-protocol",
    "src",
    "embedagent_protocol",
)


class ProtocolPackageImportTests(unittest.TestCase):
    def _protocol_python_files(self):
        self.assertTrue(os.path.isdir(PROTOCOL_SOURCE))
        for dirpath, _dirnames, filenames in os.walk(PROTOCOL_SOURCE):
            for filename in filenames:
                if filename.endswith(".py"):
                    yield os.path.join(dirpath, filename)

    def test_protocol_has_no_core_host_or_product_imports(self):
        offenders = []
        forbidden = ("embedagent_core", "embedagent_host", "embedagent")
        for path in self._protocol_python_files():
            with open(path, "r", encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.ImportFrom):
                    modules.append(node.module or "")
                elif isinstance(node, ast.Import):
                    modules.extend(alias.name for alias in node.names)
                for module in modules:
                    if any(module == name or module.startswith(name + ".") for name in forbidden):
                        offenders.append((os.path.relpath(path, PROTOCOL_SOURCE), module))
        self.assertEqual(offenders, [])

    def test_protocol_imports_from_an_isolated_package_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            shutil.copytree(PROTOCOL_SOURCE, os.path.join(temp_dir, "embedagent_protocol"))
            script = """
import pathlib
import sys

root = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
from embedagent_protocol import CoreInterface, PermissionContext
import embedagent_protocol

package_file = pathlib.Path(embedagent_protocol.__file__).resolve()
assert root in package_file.parents, package_file
assert CoreInterface is not None
assert PermissionContext is not None
for module_name in sys.modules:
    assert module_name != "embedagent"
    assert not module_name.startswith("embedagent.")
    assert module_name != "embedagent_host"
    assert not module_name.startswith("embedagent_host.")
    assert module_name != "embedagent_core"
    assert not module_name.startswith("embedagent_core.")
"""
            result = subprocess.run(
                [sys.executable, "-I", "-S", "-c", script, temp_dir],
                cwd=temp_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_protocol_source_is_owned_only_by_workspace_distribution(self):
        self.assertTrue(os.path.isdir(PROTOCOL_SOURCE))
        self.assertFalse(os.path.exists(os.path.join(ROOT, "src", "embedagent", "protocol")))


if __name__ == "__main__":
    unittest.main()
