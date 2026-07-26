import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class AgentProfileTests(unittest.TestCase):
    def test_profile_contract_is_core_owned_and_canonicalizes_sequences(self):
        from embedagent_core.profile import AgentModeDescriptor, AgentProfile

        allowed_tools = ["read_file"]
        writable_globs = ["**/*.md"]
        modes = [
            AgentModeDescriptor(
                slug="explore",
                label="Explore",
                description="Read project context.",
                system_prompt="Read only.",
                allowed_tools=allowed_tools,
                writable_globs=writable_globs,
            )
        ]

        profile = AgentProfile(
            profile_id="tests.base",
            label="Base",
            default_mode="",
            modes=modes,
        )

        allowed_tools.append("write_file")
        writable_globs.append("**/*.py")
        modes.clear()

        self.assertEqual(profile.default_mode, "")
        self.assertEqual(profile.modes, (profile.require_mode("explore"),))
        self.assertIsInstance(profile.modes, tuple)
        self.assertEqual(profile.modes[0].allowed_tools, ("read_file",))
        self.assertIsInstance(profile.modes[0].allowed_tools, tuple)
        self.assertEqual(profile.modes[0].writable_globs, ("**/*.md",))
        self.assertIsInstance(profile.modes[0].writable_globs, tuple)

    def test_profile_contract_is_frozen(self):
        from dataclasses import FrozenInstanceError

        from embedagent_core.profile import AgentModeDescriptor, AgentProfile

        mode = AgentModeDescriptor("explore", "Explore", "Read.", "Read only.")
        profile = AgentProfile("tests.base", "Base", "", [mode])

        with self.assertRaises(FrozenInstanceError):
            mode.allowed_tools = ("write_file",)
        with self.assertRaises(FrozenInstanceError):
            profile.modes = ()

    def test_c_cpp_profile_declares_current_product_modes(self):
        from embedagent_workflow_cpp.profile import (
            default_cpp_profile,
        )

        profile = default_cpp_profile()
        self.assertEqual(profile.default_mode, "explore")
        self.assertEqual(
            [item.slug for item in profile.modes],
            ["explore", "spec", "build", "debug", "verify"],
        )

    def test_profile_base_tools_exclude_c_workflow_tools(self):
        from embedagent_workflow_cpp.profile import (
            default_cpp_profile,
        )

        profile = default_cpp_profile()
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
        from embedagent_workflow_cpp.profile import (
            default_cpp_profile,
        )

        profile = default_cpp_profile()
        payload = profile.mode_descriptor_payloads()
        build = [item for item in payload if item["id"] == "build"][0]
        self.assertEqual([item["order"] for item in payload], [0, 1, 2, 3, 4])
        self.assertEqual(build["label"], "Build")
        self.assertEqual(build["dispatch"], {"kind": "mode.set", "mode": "build"})
        self.assertEqual(build["source_type"], "agent_profile")
        self.assertEqual(build["source_id"], profile.profile_id)

    def test_builtin_profile_color_tokens_are_generic_not_mode_names(self):
        from embedagent_host.runtime.profiles import (
            generic_agent_profile,
            html_agent_profile,
            python_agent_profile,
        )
        from embedagent_workflow_cpp.profile import (
            default_cpp_profile,
        )

        profiles = [
            default_cpp_profile(),
            generic_agent_profile(),
            python_agent_profile(),
            html_agent_profile(),
        ]
        for profile in profiles:
            tokens = [item.color_token for item in profile.modes]
            self.assertNotIn("verify", tokens)

    def test_unknown_mode_raises_in_profile_lookup(self):
        from embedagent_workflow_cpp.profile import (
            default_cpp_profile,
        )

        profile = default_cpp_profile()
        with self.assertRaises(ValueError):
            profile.require_mode("python-build")

    def test_agent_profile_runtime_policy_renders_and_routes_profile_modes(self):
        from embedagent_core.profile_runtime import AgentProfileRuntimePolicy
        from embedagent_host.runtime.profiles import python_agent_profile

        policy = AgentProfileRuntimePolicy(python_agent_profile())

        prompt = policy.build_system_prompt("build")
        self.assertIn("Python 工程", prompt)
        self.assertIn("Current mode: build", prompt)
        self.assertEqual(
            policy.parse_mode_switch_request("/mode debug fix it", "explore"),
            ("debug", "fix it", True),
        )
        self.assertEqual(
            policy.parse_mode_switch_request("切换到verify模式", "explore"),
            ("verify", "", True),
        )

    def test_agent_profile_runtime_prompt_frame_is_product_neutral(self):
        from embedagent_core.profile_runtime import AgentProfileRuntimePolicy
        from embedagent_host.runtime.profiles import python_agent_profile

        prompt = AgentProfileRuntimePolicy(python_agent_profile()).build_system_prompt("build")

        self.assertIn("Current mode: build", prompt)
        self.assertIn("answer in the user's language", prompt)
        self.assertNotIn("EmbedAgent", prompt)
        self.assertNotIn("优先用中文", prompt)

    def test_base_agent_profiles_do_not_export_c_cpp_specialization(self):
        import embedagent_host.runtime.profiles as profiles

        self.assertFalse(hasattr(profiles, "default_c_cpp_agent_profile"))

        module_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "packages",
            "embedagent-host",
            "src",
            "embedagent_host",
            "runtime",
            "profiles.py",
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
        from embedagent_host.runtime.profiles import (
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
