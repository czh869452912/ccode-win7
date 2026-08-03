import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class HostPackageCompositionTests(unittest.TestCase):
    def test_host_package_uses_agent_application_loader_for_default_composition(self):
        import embedagent_host
        from embedagent_host.inprocess_adapter import InProcessAdapter
        from embedagent_host.runtime.agent_applications import build_agent_application

        self.assertIsNotNone(embedagent_host)
        self.assertIsNotNone(InProcessAdapter)
        self.assertTrue(callable(build_agent_application))

        adapter_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "packages",
            "embedagent-host",
            "src",
            "embedagent_host",
            "inprocess_adapter.py",
        )
        with open(adapter_path, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("build_agent_application", source)
        self.assertIn("base_agent_application_registry", source)
        self.assertNotIn("product_agent_application_registry", source)
        self.assertNotIn("build_default_extension_set", source)
        self.assertNotIn("default_c_cpp_agent_profile", source)
        self.assertNotIn("_refresh_harness_state", source)
        self.assertNotIn("refresh_harness_state=", source)

        command_service_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "packages",
            "embedagent-host",
            "src",
            "embedagent_host",
            "hosted_command_service.py",
        )
        with open(command_service_path, "r", encoding="utf-8") as handle:
            command_service_source = handle.read()
        self.assertNotIn("refresh_harness_state", command_service_source)
        self.assertNotIn("_refresh_harness_state", command_service_source)

    def test_base_agent_application_registry_is_profile_only(self):
        from embedagent_host.runtime.agent_applications import (
            GENERIC_AGENT_APPLICATION_ID,
            available_agent_application_manifests,
            build_agent_application,
        )
        from embedagent_host.runtime.tools import ToolRuntime

        manifests = available_agent_application_manifests()
        manifest_by_id = dict((item.application_id, item) for item in manifests)

        self.assertNotIn("embedagent.default_c_cpp", manifest_by_id)
        self.assertIn(GENERIC_AGENT_APPLICATION_ID, manifest_by_id)

        with tempfile.TemporaryDirectory() as workspace:
            application = build_agent_application("", ToolRuntime(workspace))

        self.assertEqual(application.application_id, GENERIC_AGENT_APPLICATION_ID)
        self.assertEqual(application.manifest.workflow_package_ids, ())

    def test_product_agent_application_registry_exposes_default_c_cpp_manifest(self):
        from embedagent_host.runtime.agent_applications import (
            available_agent_application_manifests,
            build_agent_application,
        )
        from embedagent_host.runtime.tools import ToolRuntime

        from embedagent.product_catalog import (
            DEFAULT_C_CPP_AGENT_APPLICATION_ID,
            product_agent_application_registry,
        )

        registry = product_agent_application_registry()
        manifests = available_agent_application_manifests(registry)
        manifest_by_id = dict((item.application_id, item) for item in manifests)

        self.assertIn(DEFAULT_C_CPP_AGENT_APPLICATION_ID, manifest_by_id)
        default_manifest = manifest_by_id[DEFAULT_C_CPP_AGENT_APPLICATION_ID]
        self.assertEqual(default_manifest.label, "Default C/C++ Agent")
        self.assertEqual(default_manifest.profile_id, "embedagent.default_c_cpp")
        self.assertEqual(default_manifest.workflow_package_ids, ("embedagent.c_workflow",))
        self.assertEqual(
            default_manifest.to_dict()["applicationId"],
            DEFAULT_C_CPP_AGENT_APPLICATION_ID,
        )

        with tempfile.TemporaryDirectory() as workspace:
            application = build_agent_application(
                "",
                ToolRuntime(workspace),
                registry=registry,
            )

        self.assertEqual(application.application_id, DEFAULT_C_CPP_AGENT_APPLICATION_ID)
        self.assertEqual(
            application.manifest.application_id,
            DEFAULT_C_CPP_AGENT_APPLICATION_ID,
        )

    def test_agent_application_registry_exposes_builtin_non_c_applications(self):
        from embedagent_host.runtime.agent_applications import (
            agent_application_capability_payload,
            available_agent_application_manifests,
            build_agent_application,
        )
        from embedagent_host.runtime.tools import ToolRuntime

        manifests = available_agent_application_manifests()
        manifest_by_id = dict((item.application_id, item) for item in manifests)

        self.assertIn("embedagent.generic", manifest_by_id)
        self.assertIn("embedagent.python", manifest_by_id)
        self.assertIn("embedagent.html", manifest_by_id)
        self.assertNotIn("embedagent.default_c_cpp", manifest_by_id)
        self.assertEqual(manifest_by_id["embedagent.generic"].workflow_package_ids, ())
        self.assertEqual(manifest_by_id["embedagent.python"].workflow_package_ids, ())
        self.assertEqual(manifest_by_id["embedagent.html"].workflow_package_ids, ())

        with tempfile.TemporaryDirectory() as workspace:
            python_app = build_agent_application("embedagent.python", ToolRuntime(workspace))
            html_app = build_agent_application("embedagent.html", ToolRuntime(workspace))

        self.assertEqual(python_app.profile.profile_id, "embedagent.python")
        self.assertEqual(html_app.profile.profile_id, "embedagent.html")
        self.assertEqual(python_app.manifest.workflow_package_ids, ())
        self.assertEqual(html_app.manifest.workflow_package_ids, ())
        self.assertEqual(python_app.extension_manager.package_manifests(), [])
        self.assertEqual(html_app.extension_manager.package_manifests(), [])

        payload = agent_application_capability_payload("embedagent.python")
        available = dict((item["applicationId"], item) for item in payload["agentApplications"])
        self.assertEqual(payload["agentApplication"]["applicationId"], "embedagent.python")
        self.assertEqual(payload["agentApplication"]["profileId"], "embedagent.python")
        self.assertTrue(payload["agentApplication"]["active"])
        self.assertTrue(available["embedagent.python"]["active"])
        self.assertNotIn("embedagent.default_c_cpp", available)
        self.assertEqual(payload["emptyState"]["scenario_label"], "Python workspace")
        self.assertEqual(payload["emptyState"]["primary"], "Open a Python project")
        self.assertNotIn("appShell", payload["agentApplication"]["metadata"])

    def test_agent_application_registry_uses_explicit_runtime_factories(self):
        module_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "packages",
            "embedagent-host",
            "src",
            "embedagent_host",
            "runtime",
            "agent_applications.py",
        )
        with open(module_path, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn("class AgentApplicationRecord", source)
        self.assertIn("class AgentApplicationRegistry", source)
        self.assertIn("BUILTIN_AGENT_APPLICATION_RECORDS", source)
        self.assertNotIn("builder_path", source)
        self.assertNotIn("profile_kind", source)
        self.assertNotIn('== "c_cpp"', source)
        self.assertNotIn("_lazy_agent_application_records", source)
        self.assertNotIn("default_c_cpp_application_record", source)
        self.assertNotIn("embedagent_workflow_cpp", source)
        self.assertNotIn("from embedagent_workflow_cpp.component import", source)

    def test_importing_base_agent_application_registry_does_not_load_c_workflow(self):
        repo_src = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "src"))
        script = (
            "import sys, tempfile\n"
            "sys.path.insert(0, %r)\n"
            "from embedagent_host.runtime.agent_applications import build_agent_application\n"
            "from embedagent_host.runtime.tools import ToolRuntime\n"
            "with tempfile.TemporaryDirectory() as workspace:\n"
            "    build_agent_application('embedagent.generic', ToolRuntime(workspace))\n"
            "loaded = any(name.startswith('embedagent_workflow_cpp') for name in sys.modules)\n"
            "raise SystemExit(1 if loaded else 0)\n"
        ) % repo_src

        result = subprocess.run(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_default_c_cpp_application_record_is_package_owned(self):
        root = os.path.join(os.path.dirname(__file__), "..")
        registry_path = os.path.join(
            root,
            "packages",
            "embedagent-host",
            "src",
            "embedagent_host",
            "runtime",
            "agent_applications.py",
        )
        record_path = os.path.join(
            root,
            "src",
            "embedagent",
            "product_catalog.py",
        )
        self.assertTrue(os.path.isfile(record_path))

        with open(registry_path, "r", encoding="utf-8") as handle:
            registry_source = handle.read()
        with open(record_path, "r", encoding="utf-8") as handle:
            record_source = handle.read()

        self.assertNotIn("_C_CPP_APP_SHELL", registry_source)
        for token in ('"Default C/C++ Agent"', '"Path to C/C++ project"'):
            self.assertNotIn(token, registry_source)
            self.assertIn(token, record_source)
        self.assertNotIn('"embedagent.c_workflow"', registry_source)
        self.assertNotIn("embedagent_workflow_cpp", registry_source)
        self.assertNotIn("default_c_cpp_application_record", registry_source)
        self.assertIn("C_WORKFLOW_PACKAGE_ID", record_source)
        self.assertNotIn('profile_kind="default_c_cpp"', registry_source)
        self.assertIn("runtime_factory=cpp_runtime_definition", record_source)

    def test_default_application_compatibility_wrapper_is_removed(self):
        import embedagent_host.runtime.agent_applications as agent_applications

        module_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "packages",
            "embedagent-host",
            "src",
            "embedagent_host",
            "runtime",
            "agent_applications.py",
        )
        with open(module_path, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertFalse(hasattr(agent_applications, "build_default_agent_application"))
        self.assertNotIn("build_default_agent_application", source)

    def test_agent_application_registry_rejects_unknown_application_id(self):
        from embedagent_host.runtime.agent_applications import build_agent_application
        from embedagent_host.runtime.tools import ToolRuntime

        with tempfile.TemporaryDirectory() as workspace:
            with self.assertRaises(ValueError):
                build_agent_application("missing.application", ToolRuntime(workspace))

    def test_host_default_extension_compatibility_module_is_removed(self):
        module_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "packages",
            "embedagent-host",
            "src",
            "embedagent_host",
            "default_extensions.py",
        )
        self.assertFalse(os.path.exists(module_path))

    def test_inprocess_adapter_accepts_non_c_agent_application(self):
        from embedagent_core.extensions import ExtensionManager
        from embedagent_core.profile import AgentModeDescriptor, AgentProfile
        from embedagent_host.inprocess_adapter import InProcessAdapter
        from embedagent_host.runtime.agent_applications import AgentApplication
        from embedagent_host.runtime.tools import ToolRuntime

        profile = AgentProfile(
            profile_id="tests.python",
            label="Python Agent",
            default_mode="python-build",
            modes=[
                AgentModeDescriptor(
                    slug="python-build",
                    label="Python Build",
                    description="Python implementation mode.",
                    system_prompt="Build Python code.",
                    allowed_tools=["read_file", "write_file", "ask_user"],
                    writable_globs=["**/*.py"],
                    icon_key="python",
                    color_token="success",
                )
            ],
        )
        with tempfile.TemporaryDirectory() as workspace:
            application = AgentApplication(
                application_id="tests.python",
                label="Python Agent",
                profile=profile,
                extension_manager=ExtensionManager(),
            )
            adapter = InProcessAdapter(
                tools=ToolRuntime(workspace),
                agent_application=application,
            )

            snapshot = adapter.create_session()
            command_snapshot = adapter.submit_user_message(
                session_id=snapshot["session_id"],
                text="/mode python-build",
                stream=False,
                wait=True,
            )
            capabilities = adapter.get_session_capabilities(snapshot["session_id"])

        self.assertEqual(snapshot["current_mode"], "python-build")
        self.assertEqual(command_snapshot["current_mode"], "python-build")
        self.assertEqual(capabilities["modes"][0]["id"], "python-build")
        self.assertEqual(capabilities["modes"][0]["label"], "Python Build")
        self.assertNotIn("C/C++", str(capabilities))

    def test_inprocess_adapter_uses_shared_agent_profile_runtime_policies(self):
        module_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "packages",
            "embedagent-host",
            "src",
            "embedagent_host",
            "inprocess_adapter.py",
        )
        with open(module_path, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn("AgentProfileRuntimePolicy", source)
        self.assertIn("AgentProfileToolPolicy", source)
        self.assertIn("AgentProfileWritePathPolicy", source)
        for token in (
            "class _ProductModeToolPolicy",
            "class _ProductWritePathPolicy",
            "class _ProductModeRuntimePolicy",
            "_profile_writable_globs",
            "你是 EmbedAgent 的受控模式原型。",
        ):
            self.assertNotIn(token, source)

    def test_inprocess_adapter_loads_application_by_id(self):
        from embedagent_host.inprocess_adapter import InProcessAdapter
        from embedagent_host.runtime.tools import ToolRuntime

        from embedagent.product_catalog import (
            DEFAULT_C_CPP_AGENT_APPLICATION_ID,
            product_agent_application_registry,
        )

        with tempfile.TemporaryDirectory() as workspace:
            adapter = InProcessAdapter(
                tools=ToolRuntime(workspace),
                agent_application_id=DEFAULT_C_CPP_AGENT_APPLICATION_ID,
                agent_application_registry=product_agent_application_registry(),
            )
            capabilities = adapter.get_session_capabilities()

        self.assertEqual(
            adapter.agent_application.application_id,
            DEFAULT_C_CPP_AGENT_APPLICATION_ID,
        )
        self.assertEqual(
            adapter.agent_application.manifest.workflow_package_ids,
            ("embedagent.c_workflow",),
        )
        self.assertEqual(
            capabilities["agentApplication"]["applicationId"],
            DEFAULT_C_CPP_AGENT_APPLICATION_ID,
        )
        self.assertEqual(
            capabilities["agentApplications"][0]["applicationId"],
            DEFAULT_C_CPP_AGENT_APPLICATION_ID,
        )

    def test_inprocess_adapter_loads_builtin_non_c_application_by_id(self):
        from embedagent_host.inprocess_adapter import InProcessAdapter
        from embedagent_host.runtime.tools import ToolRuntime

        with tempfile.TemporaryDirectory() as workspace:
            adapter = InProcessAdapter(
                tools=ToolRuntime(workspace),
                agent_application_id="embedagent.python",
            )
            session = adapter.create_session()
            capabilities = adapter.get_session_capabilities(session["session_id"])

        active = capabilities["agentApplication"]
        available = dict(
            (item["applicationId"], item) for item in capabilities["agentApplications"]
        )
        self.assertEqual(session["current_mode"], "explore")
        self.assertEqual(active["applicationId"], "embedagent.python")
        self.assertEqual(active["workflowPackageIds"], [])
        self.assertTrue(available["embedagent.python"]["active"])
        self.assertNotIn("embedagent.default_c_cpp", available)
        self.assertIn("embedagent.html", available)
        self.assertEqual(
            [mode["id"] for mode in capabilities["modes"]],
            ["explore", "spec", "build", "debug", "verify"],
        )
        self.assertEqual(capabilities["workflowPackages"], [])

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
