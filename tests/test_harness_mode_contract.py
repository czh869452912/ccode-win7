import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.modes import PermissionContract, get_mode_contract


class TestPermissionContract(unittest.TestCase):
    def test_explore_is_read_only(self):
        contract = get_mode_contract("explore")
        self.assertTrue(contract.read_only)
        self.assertFalse(contract.is_path_writable("test.py"))

    def test_build_allows_write(self):
        contract = get_mode_contract("build")
        self.assertFalse(contract.read_only)
        self.assertTrue(contract.allows_tool("write_file"))
        self.assertTrue(contract.requires_permission("write_file"))

    def test_build_allows_edit(self):
        contract = get_mode_contract("build")
        self.assertTrue(contract.allows_tool("edit_file"))

    def test_verify_is_read_only(self):
        contract = get_mode_contract("verify")
        self.assertTrue(contract.read_only)
        self.assertFalse(contract.allows_tool("write_file"))

    def test_debug_requires_permission_for_edit(self):
        contract = get_mode_contract("debug")
        self.assertTrue(contract.requires_permission("edit_file"))

    def test_unknown_mode_defaults_to_explore(self):
        contract = get_mode_contract("nonexistent")
        self.assertTrue(contract.read_only)


class TestHarnessInjection(unittest.TestCase):
    def test_chat_does_not_trigger_harness(self):
        from embedagent.query_engine import QueryEngine
        engine = QueryEngine.__new__(QueryEngine)
        # Chat messages should not trigger harness
        self.assertFalse(engine._should_inject_harness("hi", "build"))
        self.assertFalse(engine._should_inject_harness("hello", "build"))
        self.assertFalse(engine._should_inject_harness("what can you do?", "build"))

    def test_work_request_triggers_harness(self):
        from embedagent.query_engine import QueryEngine
        engine = QueryEngine.__new__(QueryEngine)
        # Work requests should trigger harness
        self.assertTrue(engine._should_inject_harness("build the project", "build"))
        self.assertTrue(engine._should_inject_harness("fix this bug", "debug"))

    def test_explore_never_triggers_harness(self):
        from embedagent.query_engine import QueryEngine
        engine = QueryEngine.__new__(QueryEngine)
        self.assertFalse(engine._should_inject_harness("build the project", "explore"))


if __name__ == "__main__":
    unittest.main()
