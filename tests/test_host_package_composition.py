import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class HostPackageCompositionTests(unittest.TestCase):
    def test_host_package_owns_inprocess_adapter_and_default_workflow_assembly(self):
        import embedagent_host
        from embedagent_host.default_extensions import build_default_extension_set
        from embedagent_host.inprocess_adapter import InProcessAdapter

        self.assertIsNotNone(embedagent_host)
        self.assertIsNotNone(InProcessAdapter)
        self.assertTrue(callable(build_default_extension_set))

    def test_product_root_does_not_keep_core_or_host_module_aliases(self):
        root = os.path.join(os.path.dirname(__file__), "..", "src", "embedagent")
        removed_modules = (
            "agent_loop.py",
            "agent_kernel.py",
            "agent_tool_action_service.py",
            "default_extensions.py",
            "hosted_command_service.py",
            "hosted_interaction_service.py",
            "inprocess_adapter.py",
            "query_engine.py",
        )
        offenders = [name for name in removed_modules if os.path.exists(os.path.join(root, name))]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
