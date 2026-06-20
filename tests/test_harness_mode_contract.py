import os
import sys
import unittest

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.modes import get_mode_contract


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


@pytest.mark.harness
class TestHarnessInjection(unittest.TestCase):
    def _make_extension(self):
        from embedagent.harness.extension import CHarnessWorkflowExtension

        return CHarnessWorkflowExtension()

    def test_chat_does_not_trigger_harness(self):
        extension = self._make_extension()
        # Chat messages should not trigger harness
        self.assertFalse(extension.should_inject_workflow("hi", "build"))
        self.assertFalse(extension.should_inject_workflow("hello", "build"))
        self.assertFalse(extension.should_inject_workflow("what can you do?", "build"))
        self.assertFalse(extension.should_inject_workflow("你好", "build"))
        self.assertFalse(extension.should_inject_workflow("你能做什么？", "debug"))

    def test_work_request_triggers_harness(self):
        extension = self._make_extension()
        # Work requests should trigger harness
        self.assertTrue(extension.should_inject_workflow("build the project", "build"))
        self.assertTrue(extension.should_inject_workflow("fix this bug", "debug"))
        self.assertTrue(extension.should_inject_workflow("帮我实现一个排序函数", "build"))
        self.assertTrue(extension.should_inject_workflow("帮我定位这个崩溃", "debug"))
        self.assertTrue(extension.should_inject_workflow("运行测试并检查失败原因", "build"))

    def test_explore_never_triggers_harness(self):
        extension = self._make_extension()
        self.assertFalse(extension.should_inject_workflow("build the project", "explore"))


if __name__ == "__main__":
    unittest.main()
