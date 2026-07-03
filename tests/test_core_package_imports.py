import ast
import os
import sys
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
                if module == "embedagent" or module.startswith("embedagent."):
                    offenders.append((os.path.relpath(path, root), module))
                    continue
        self.assertEqual(offenders, [])

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
