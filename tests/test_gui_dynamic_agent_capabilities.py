import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WEBAPP_SOURCE = REPO_ROOT / "src" / "embedagent" / "frontend" / "gui" / "webapp" / "src"
FORBIDDEN_RENDERER_LITERALS = re.compile(
    r"\b(?:bash|read_file|write_file|run_recipe|report_quality_v2|"
    r"record_failing_evidence|task_status)\b|C/C\+\+|Clang|embedded C"
)

sys.path.insert(0, str(REPO_ROOT / "src"))

from embedagent.frontend.gui.backend.protocol_payloads import (  # noqa: E402
    serialize_app_bootstrap,
    serialize_session_bootstrap,
)


class GuiDynamicAgentCapabilityTests(unittest.TestCase):
    def test_base_agent_preserves_empty_dynamic_capabilities(self):
        app_payload = serialize_app_bootstrap(
            {
                "app": {"shell_version": 1, "protocol": "gui_app_shell_v1"},
                "capabilities": {
                    "empty_state": {
                        "primary": "Open a workspace",
                        "path_placeholder": r"D:\work\project",
                    }
                },
            }
        )
        session_payload = serialize_session_bootstrap(
            {
                "snapshot": {"session_id": "base-agent", "status": "idle"},
                "history": {"activities": []},
                "capabilities": {},
            }
        )

        self.assertNotIn("product_name", app_payload["app"])
        self.assertEqual(
            app_payload["capabilities"]["empty_state"]["primary"],
            "Open a workspace",
        )
        self.assertEqual(session_payload["capabilities"]["modes"], [])
        self.assertEqual(session_payload["capabilities"]["commands"], [])
        self.assertEqual(session_payload["capabilities"]["tools"], [])
        self.assertFalse(session_payload["capabilities"]["agentApplication"])

    def test_specialized_agent_preserves_generic_descriptors(self):
        app_payload = serialize_app_bootstrap(
            {
                "app": {
                    "shell_version": 1,
                    "product_name": "Project Inspector",
                    "protocol": "gui_app_shell_v1",
                },
                "capabilities": {
                    "workbench_commands": [
                        {
                            "id": "project.check",
                            "label": "Check project",
                            "group": "project",
                            "dispatch": {"kind": "slash", "command": "/check-project"},
                        }
                    ],
                    "surfaces": {
                        "right_panel": [
                            {
                                "id": "project_report",
                                "kind": "project_report",
                                "title": "Project report",
                                "body_kind": "surface_panel",
                                "panel_kind": "descriptor",
                            }
                        ]
                    },
                },
            }
        )
        session_payload = serialize_session_bootstrap(
            {
                "snapshot": {
                    "session_id": "specialized-agent",
                    "status": "idle",
                    "current_mode": "inspect",
                },
                "history": {"activities": []},
                "capabilities": {
                    "modes": [
                        {
                            "id": "inspect",
                            "label": "Inspect",
                            "description": "Inspect the active project",
                            "icon_key": "search",
                            "command_id": "mode.inspect",
                        }
                    ],
                    "commands": [
                        {
                            "id": "project.check",
                            "label": "Check project",
                            "group": "project",
                            "dispatch": {"kind": "slash", "command": "/check-project"},
                        }
                    ],
                    "tools": [
                        {
                            "name": "project_check",
                            "label": "Project check",
                            "icon_key": "search-check",
                            "renderer_key": "generic",
                            "permission_category": "toolchain_exec",
                            "metadata": {"preview_arg": "target"},
                        }
                    ],
                    "agent_application": {
                        "application_id": "tests.project-inspector",
                        "label": "Project Inspector",
                        "profile_id": "tests.project-inspector.profile",
                        "active": True,
                    },
                },
            }
        )

        self.assertEqual(app_payload["app"]["product_name"], "Project Inspector")
        self.assertEqual(
            app_payload["capabilities"]["workbench_commands"][0]["id"],
            "project.check",
        )
        self.assertEqual(
            app_payload["capabilities"]["surfaces"]["right_panel"][0]["kind"],
            "project_report",
        )
        self.assertEqual(session_payload["capabilities"]["modes"][0]["id"], "inspect")
        self.assertEqual(
            session_payload["capabilities"]["commands"][0]["id"],
            "project.check",
        )
        self.assertEqual(
            session_payload["capabilities"]["tools"][0]["name"],
            "project_check",
        )
        self.assertEqual(
            session_payload["capabilities"]["agentApplication"]["applicationId"],
            "tests.project-inspector",
        )

    def test_protocol_serializers_do_not_import_workflow_package(self):
        script = """
import sys
from embedagent.frontend.gui.backend.protocol_payloads import serialize_app_bootstrap
serialize_app_bootstrap({"app": {}, "capabilities": {}})
if "embedagent_workflow_cpp" in sys.modules:
    raise SystemExit("workflow package imported by GUI protocol serializer")
"""
        environment = dict(os.environ)
        source_path = str(REPO_ROOT / "src")
        existing_python_path = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = (
            source_path + os.pathsep + existing_python_path if existing_python_path else source_path
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(REPO_ROOT),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_production_renderer_has_no_workflow_specific_literals(self):
        findings = []
        for path in sorted(WEBAPP_SOURCE.rglob("*")):
            if path.suffix not in {".js", ".jsx", ".css", ".mjs"}:
                continue
            if path.name == "visual-debug-fixtures.js":
                continue
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                match = FORBIDDEN_RENDERER_LITERALS.search(line)
                if match:
                    findings.append(
                        "{}:{}:{}".format(
                            path.relative_to(REPO_ROOT),
                            line_number,
                            match.group(0),
                        )
                    )
        self.assertEqual(findings, [], "\n".join(findings))


if __name__ == "__main__":
    unittest.main()
