import ast
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class CorePackageImportTests(unittest.TestCase):
    def _core_python_files(self):
        root = os.path.join(os.path.dirname(__file__), "..", "src", "embedagent_core")
        self.assertTrue(os.path.isdir(root))
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                if filename.endswith(".py"):
                    yield root, os.path.join(dirpath, filename)

    def _imports_from_file(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                yield node.module or ""
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    yield alias.name

    def test_embedagent_core_imports_no_product_host_gui_or_workflow_packages(self):
        offenders = []
        for root, path in self._core_python_files():
            for module in self._imports_from_file(path):
                if module == "embedagent_core" or module.startswith("embedagent_core."):
                    continue
                if module == "embedagent_host" or module.startswith("embedagent_host."):
                    offenders.append((os.path.relpath(path, root), module))
                    continue
                if module == "embedagent_protocol" or module.startswith("embedagent_protocol."):
                    offenders.append((os.path.relpath(path, root), module))
                    continue
                if module == "embedagent" or module.startswith("embedagent."):
                    offenders.append((os.path.relpath(path, root), module))
                    continue
        self.assertEqual(offenders, [])

    def test_embedagent_core_imports_from_an_isolated_package_root(self):
        source = os.path.join(os.path.dirname(__file__), "..", "src", "embedagent_core")
        with tempfile.TemporaryDirectory() as temp_dir:
            shutil.copytree(source, os.path.join(temp_dir, "embedagent_core"))
            script = """
import pathlib
import sys

root = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
import embedagent_core
import embedagent_core.api

package_file = pathlib.Path(embedagent_core.__file__).resolve()
assert root in package_file.parents, package_file
for module_name in sys.modules:
    assert module_name != "embedagent"
    assert not module_name.startswith("embedagent.")
    assert module_name != "embedagent_host"
    assert not module_name.startswith("embedagent_host.")
    assert module_name != "embedagent_protocol"
    assert not module_name.startswith("embedagent_protocol.")
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

    def test_deleted_core_type_paths_do_not_exist_in_product_package(self):
        root = os.path.join(os.path.dirname(__file__), "..", "src", "embedagent")
        deleted = (
            "session.py",
            "interaction.py",
            "guard.py",
            "tool_execution.py",
            "compacted_history.py",
            "llm.py",
        )
        existing = [name for name in deleted if os.path.exists(os.path.join(root, name))]
        self.assertEqual(existing, [])


if __name__ == "__main__":
    unittest.main()
