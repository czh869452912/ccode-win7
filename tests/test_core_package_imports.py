import ast
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class CorePackageImportTests(unittest.TestCase):
    def test_embedagent_core_imports_no_gui_host_or_workflow_package(self):
        root = os.path.join(os.path.dirname(__file__), "..", "src", "embedagent_core")
        self.assertTrue(os.path.isdir(root))
        forbidden = (
            "embedagent.frontend",
            "embedagent_host",
            "embedagent.workflow_packages",
            "embedagent.workflow_packages.c_cpp",
        )
        offenders = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                path = os.path.join(dirpath, filename)
                with open(path, "r", encoding="utf-8") as handle:
                    tree = ast.parse(handle.read(), filename=path)
                for node in ast.walk(tree):
                    module = ""
                    if isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                    elif isinstance(node, ast.Import):
                        module = ",".join(alias.name for alias in node.names)
                    if any(item in module for item in forbidden):
                        offenders.append((os.path.relpath(path, root), module))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
