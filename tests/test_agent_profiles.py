import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class AgentProfileTests(unittest.TestCase):
    def test_c_cpp_profile_declares_current_product_modes(self):
        from embedagent.workflow_packages.c_cpp.agent_profile import (
            default_c_cpp_agent_profile,
        )

        profile = default_c_cpp_agent_profile()
        self.assertEqual(profile.default_mode, "explore")
        self.assertEqual(
            [item.slug for item in profile.modes],
            ["explore", "spec", "build", "debug", "verify"],
        )

    def test_profile_base_tools_exclude_c_workflow_tools(self):
        from embedagent.workflow_packages.c_cpp.agent_profile import (
            default_c_cpp_agent_profile,
        )

        profile = default_c_cpp_agent_profile()
        harness_tools = {
            "list_recipes",
            "run_recipe",
            "report_quality_v2",
            "record_failing_evidence",
            "task_status",
        }
        for mode_name in ("explore", "spec", "build", "debug", "verify"):
            self.assertEqual(set(profile.allowed_tools_for(mode_name)) & harness_tools, set())

    def test_profile_mode_descriptor_payload_is_gui_safe(self):
        from embedagent.workflow_packages.c_cpp.agent_profile import (
            default_c_cpp_agent_profile,
        )

        profile = default_c_cpp_agent_profile()
        payload = profile.mode_descriptor_payloads()
        build = [item for item in payload if item["id"] == "build"][0]
        self.assertEqual([item["order"] for item in payload], [0, 1, 2, 3, 4])
        self.assertEqual(build["label"], "Build")
        self.assertEqual(build["dispatch"], {"kind": "mode.set", "mode": "build"})
        self.assertEqual(build["source_type"], "agent_profile")
        self.assertEqual(build["source_id"], profile.profile_id)

    def test_builtin_profile_color_tokens_are_generic_not_mode_names(self):
        from embedagent_host.runtime.agent_profiles import (
            generic_agent_profile,
            html_agent_profile,
            python_agent_profile,
        )

        from embedagent.workflow_packages.c_cpp.agent_profile import (
            default_c_cpp_agent_profile,
        )

        profiles = [
            default_c_cpp_agent_profile(),
            generic_agent_profile(),
            python_agent_profile(),
            html_agent_profile(),
        ]
        for profile in profiles:
            tokens = [item.color_token for item in profile.modes]
            self.assertNotIn("verify", tokens)

    def test_unknown_mode_raises_in_profile_lookup(self):
        from embedagent.workflow_packages.c_cpp.agent_profile import (
            default_c_cpp_agent_profile,
        )

        profile = default_c_cpp_agent_profile()
        with self.assertRaises(ValueError):
            profile.require_mode("python-build")

    def test_agent_profile_runtime_policy_renders_and_routes_profile_modes(self):
        from embedagent_host.runtime.agent_profile_runtime import AgentProfileRuntimePolicy
        from embedagent_host.runtime.agent_profiles import python_agent_profile

        policy = AgentProfileRuntimePolicy(python_agent_profile())

        prompt = policy.build_system_prompt("build")
        self.assertIn("Python 工程", prompt)
        self.assertIn("当前模式：build", prompt)
        self.assertEqual(
            policy.parse_mode_switch_request("/mode debug fix it", "explore"),
            ("debug", "fix it", True),
        )
        self.assertEqual(
            policy.parse_mode_switch_request("切换到verify模式", "explore"),
            ("verify", "", True),
        )

    def test_base_agent_profiles_do_not_export_c_cpp_specialization(self):
        import embedagent_host.runtime.agent_profiles as profiles

        self.assertFalse(hasattr(profiles, "default_c_cpp_agent_profile"))

        module_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "packages",
            "embedagent-host",
            "src",
            "embedagent_host",
            "runtime",
            "agent_profiles.py",
        )
        with open(module_path, "r", encoding="utf-8") as handle:
            source = handle.read()
        for token in (
            "default_c_cpp_agent_profile",
            "DEVELOPMENT_WRITABLE_GLOBS",
            "CMakeLists.txt",
            "**/*.cpp",
            "**/*.hpp",
        ):
            self.assertNotIn(token, source)

    def test_builtin_non_c_profiles_are_domain_scoped(self):
        from embedagent_host.runtime.agent_profiles import (
            generic_agent_profile,
            html_agent_profile,
            python_agent_profile,
        )

        generic = generic_agent_profile()
        python = python_agent_profile()
        html = html_agent_profile()

        self.assertEqual(generic.profile_id, "embedagent.generic")
        self.assertEqual(python.profile_id, "embedagent.python")
        self.assertEqual(html.profile_id, "embedagent.html")
        self.assertEqual(
            [item.slug for item in generic.modes], ["explore", "spec", "build", "debug", "verify"]
        )
        self.assertEqual(
            [item.slug for item in python.modes], ["explore", "spec", "build", "debug", "verify"]
        )
        self.assertEqual(
            [item.slug for item in html.modes], ["explore", "spec", "build", "debug", "verify"]
        )

        self.assertIn("**/*.py", python.writable_globs_for("build"))
        self.assertNotIn("**/*.c", python.writable_globs_for("build"))
        self.assertIn("**/*.html", html.writable_globs_for("build"))
        self.assertIn("**/*.css", html.writable_globs_for("build"))
        self.assertNotIn("**/*.c", html.writable_globs_for("build"))
        self.assertIn("**/*", generic.writable_globs_for("build"))


if __name__ == "__main__":
    unittest.main()
