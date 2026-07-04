import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.agent_applications import agent_application_capability_payload
from embedagent.frontend.gui.backend.app_host import GUIAppHost
from embedagent.frontend.gui.backend.app_shell import AppShellService
from embedagent.frontend.gui.backend.app_shell_spec import AppShellSpec
from embedagent.frontend.gui.backend.workspace_registry import WorkspaceRegistry


class _FakeFrontend(object):
    def __init__(self):
        self.messages = []

    def _dispatch_message(self, message):
        self.messages.append(message)
        return True


class _FakeCore(object):
    def __init__(self, workspace):
        self.workspace = workspace
        self.frontend = None
        self.shutdown_calls = 0

    def register_frontend(self, frontend):
        self.frontend = frontend

    def shutdown(self):
        self.shutdown_calls += 1

    def list_sessions(self, limit=10):
        raise AssertionError("app shell must not read session history")

    def get_session_bootstrap(self, session_id):
        raise AssertionError("app shell must not read session bootstrap")

    def get_session_capabilities(self, session_id=""):
        return {
            "agentApplication": {
                "applicationId": "tests.python",
                "label": "Python Agent",
                "profileId": "tests.python.profile",
                "workflowPackageIds": ["tests.python.workflow"],
                "active": True,
            },
            "agentApplications": [
                {
                    "applicationId": "tests.python",
                    "label": "Python Agent",
                    "profileId": "tests.python.profile",
                    "workflowPackageIds": ["tests.python.workflow"],
                    "active": True,
                }
            ],
            "emptyState": {
                "scenario_label": "Python workspace",
                "primary": "Open a Python project",
            },
        }

    def get_workspace_snapshot(self):
        return {"path": self.workspace}


class TestGuiAppShellService(unittest.TestCase):
    def _service(
        self,
        registry,
        created,
        host_diagnostics=None,
        shell_spec=None,
        agent_capabilities=None,
    ):
        def factory(path):
            core = _FakeCore(path)
            created.append(core)
            return core

        host = GUIAppHost(
            core_factory=factory,
            registry=registry,
            agent_capabilities=agent_capabilities,
        )
        frontend = _FakeFrontend()
        host.bind_frontend(frontend)
        return (
            AppShellService(
                host,
                host_diagnostics=host_diagnostics
                or {
                    "host": {"platform": "win32", "debug": False},
                    "runtime": {
                        "runtime_source": "bundle",
                        "runtime_path": r"C:\runtime\webview2",
                    },
                    "renderer": {"renderer": "edgechromium"},
                },
                shell_spec=shell_spec,
            ),
            host,
            frontend,
        )

    def test_bootstrap_without_workspace_includes_shell_fields(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            service, host, frontend = self._service(registry, [])

            payload = service.bootstrap()

        self.assertEqual(payload["app"]["shell_version"], 1)
        self.assertEqual(payload["app"]["protocol"], "gui_app_shell_v1")
        self.assertEqual(payload["app"]["product_name"], "EmbedAgent")
        self.assertEqual(payload["has_active_workspace"], False)
        self.assertIsNone(payload["active_workspace"])
        self.assertEqual(payload["workspaces"], [])
        app_command_ids = [item["id"] for item in payload["capabilities"]["app_commands"]]
        self.assertIn("app.settings", app_command_ids)
        self.assertIn("app.diagnostics", app_command_ids)
        self.assertIn("app.source_control", app_command_ids)
        self.assertIn("app.reload", app_command_ids)
        workbench_command_ids = [
            item["id"] for item in payload["capabilities"]["workbench_commands"]
        ]
        self.assertIn("message.send", workbench_command_ids)
        self.assertIn("palette.open", workbench_command_ids)
        self.assertIn("view.toggle_right_panel", workbench_command_ids)
        self.assertNotIn("workflow.diff", workbench_command_ids)
        keybinding_commands = [
            item["command_id"] for item in payload["capabilities"]["keybindings"]
        ]
        self.assertIn("palette.open", keybinding_commands)
        self.assertIn("surface.files", keybinding_commands)
        self.assertIn("app.settings", keybinding_commands)
        right_panel_surfaces = [
            item["id"] for item in payload["capabilities"]["surfaces"]["right_panel"]
        ]
        self.assertIn("settings", right_panel_surfaces)
        self.assertIn("diagnostics", right_panel_surfaces)
        self.assertIn("source_control", right_panel_surfaces)
        self.assertEqual(
            payload["capabilities"]["surfaces"]["right_panel"][0]["launcher_order"],
            10,
        )
        self.assertEqual(
            payload["capabilities"]["surfaces"]["chrome"]["empty_title"],
            "Open a surface",
        )
        self.assertEqual(
            payload["capabilities"]["surfaces"]["chrome"]["close_all_action_label"],
            "Close all",
        )
        self.assertEqual(
            payload["capabilities"]["surfaces"]["chrome"]["bottom_drawer_aria_label"],
            "Bottom drawer",
        )
        self.assertEqual(
            payload["capabilities"]["surfaces"]["chrome"]["run_output_empty_message"],
            "No run output yet.",
        )
        self.assertEqual(
            payload["capabilities"]["surfaces"]["chrome"]["termination_reason_prefix"],
            "reason",
        )
        self.assertEqual(
            payload["capabilities"]["surfaces"]["chrome"]["file_preview"],
            {
                "default_file_title": "File",
                "default_project_label": "Workspace",
                "loading_message": "Loading file...",
                "unavailable_message": "File unavailable",
                "retry_label": "Retry",
                "copy_path_title_template": "Copy {title} path",
                "show_markdown_source_label": "Show markdown source",
                "show_rendered_markdown_label": "Show rendered markdown",
                "show_file_explorer_label": "Show file explorer",
                "metadata_separator": " / ",
                "line_singular_label": "line",
                "line_plural_label": "lines",
                "plain_language_label": "Plain",
                "language_labels": {
                    "c": "C",
                    "c_header": "C Header",
                    "cpp": "C++",
                    "cpp_header": "C++ Header",
                    "python": "Python",
                    "javascript": "JavaScript",
                    "typescript": "TypeScript",
                    "json": "JSON",
                    "markdown": "Markdown",
                    "css": "CSS",
                    "html": "HTML",
                    "shell": "Shell",
                    "powershell": "PowerShell",
                    "toml": "TOML",
                    "yaml": "YAML",
                    "text": "Text",
                },
            },
        )
        self.assertEqual(
            payload["capabilities"]["chrome"]["timeline"],
            {
                "aria_label": "Conversation",
                "empty_state": "No conversation yet.",
                "history_partial_label": "history partially restored",
                "history_partial_fallback": "restore stopped early",
                "history_unavailable": "session history unavailable",
                "explicit_loop_limit_reached": "Explicit loop safety limit reached.",
                "max_turn_limit_template": "Maximum turn limit reached ({turnsUsed}/{maxTurns}).",
                "guard_stopped": "Stopped by guard.",
                "cancelled": "Cancelled.",
                "changed_files": {
                    "summary_template": "{count} changed files",
                    "expand_label": "Expand",
                    "collapse_label": "Collapse",
                    "view_diff_label": "View diff",
                },
                "work_group": {
                    "singular_label": "1 tool call",
                    "plural_label_template": "{count} tool calls",
                    "show_fewer_label": "Show fewer tool calls",
                    "previous_singular_template": "+{count} previous tool call",
                    "previous_plural_template": "+{count} previous tool calls",
                },
                "activity_rows": {
                    "working_label": "Working...",
                    "working_active_prefix": "Working for",
                    "turn_fold_label": "Worked for this turn",
                    "turn_fold_duration_template": "Worked for {duration}",
                    "turn_fold_stopped_duration_template": "You stopped after {duration}",
                    "turn_fold_stopped_label": "You stopped this response",
                    "turn_fold_step_singular_template": "{count} step",
                    "turn_fold_step_plural_template": "{count} steps",
                    "interaction_label": "interaction",
                    "interaction_pending_status": "pending",
                    "reasoning_label": "Thinking",
                    "thinking_label": "Thinking",
                    "streaming_status": "streaming",
                    "word_singular_template": "{count} word",
                    "word_plural_template": "{count} words",
                    "context_updated": "Context updated",
                    "context_summarized_template": "{count} summarized",
                    "context_retained_template": "{count} retained",
                    "context_size_template": "~{count} units",
                    "metadata_separator": " / ",
                    "command_default_name": "command",
                    "command_failed_status": "failed",
                    "command_completed_status": "completed",
                    "review_label": "/review",
                    "review_singular_finding": "1 finding",
                    "review_plural_findings_template": "{count} findings",
                    "timer_zero_label": "0s",
                    "timer_seconds_template": "{seconds}s",
                    "timer_minutes_seconds_template": "{minutes}m {seconds}s",
                    "timer_hours_minutes_template": "{hours}h {minutes}m",
                },
                "tool_detail": {
                    "default_section_title": "Details",
                    "fallback_match_label": "match",
                    "field_labels": {
                        "path": "path",
                        "pattern": "pattern",
                        "recipe": "recipe",
                        "target": "target",
                        "command": "command",
                        "cwd": "cwd",
                        "exit": "exit",
                        "lines": "lines",
                        "chars": "chars",
                        "matches": "matches",
                        "returned": "returned",
                    },
                    "section_titles": {
                        "error": "Error",
                        "preview": "Preview",
                        "summary": "Summary",
                        "matches": "Matches",
                        "files": "Files",
                        "stdout": "stdout",
                        "stderr": "stderr",
                        "diff": "Diff",
                        "changed_files": "Changed files",
                    },
                },
                "work_row": {
                    "default_heading": "Work",
                    "default_icon_name": "zap",
                    "status_labels": {
                        "failure": "failed",
                        "success": "completed",
                        "neutral": "empty",
                        "interrupted": "cancelled",
                        "discarded": "skipped",
                    },
                },
            },
        )
        self.assertEqual(
            payload["capabilities"]["surfaces"]["chrome"]["diff_panel"],
            {
                "default_title": "Diff",
                "empty_message": "No diff selected.",
                "selection_aria_label": "Diff selection",
                "controls_aria_label": "Diff controls",
                "stacked_title": "Stacked diff view",
                "split_title": "Split diff view",
                "enable_word_wrap_title": "Enable line wrapping",
                "disable_word_wrap_title": "Disable line wrapping",
                "hide_whitespace_title": "Hide whitespace changes",
                "show_whitespace_title": "Show whitespace changes",
                "changed_files_aria_label": "Changed files",
                "files_label": "Files",
                "expand_file_label_template": "Expand {path}",
                "collapse_file_label_template": "Collapse {path}",
                "expand_diff_label": "Expand diff",
                "source_control_title_template": "Git Diff: {path}",
            },
        )
        self.assertEqual(
            [item["id"] for item in payload["capabilities"]["thread_lifecycle"]["actions"]],
            ["rename", "fork", "archive"],
        )
        self.assertEqual(
            [item["id"] for item in payload["capabilities"]["command_palette"]["groups"]],
            [
                "app",
                "session",
                "message",
                "mode",
                "surface",
                "workspace",
                "workflow",
                "view",
            ],
        )
        self.assertEqual(
            payload["capabilities"]["command_palette"]["groups"][0]["title"],
            "App",
        )
        self.assertEqual(
            payload["capabilities"]["command_palette"]["labels"]["root_title"],
            "Command palette",
        )
        self.assertEqual(
            payload["capabilities"]["command_palette"]["labels"]["current_label"],
            "Current",
        )
        self.assertEqual(
            payload["capabilities"]["chrome"]["brand_subtitle"],
            "Local agent workbench",
        )
        self.assertEqual(
            payload["capabilities"]["chrome"]["header"]["command_palette_short_label"],
            "Cmd",
        )
        self.assertEqual(
            payload["capabilities"]["chrome"]["composer"]["placeholder"],
            "Message",
        )
        self.assertEqual(
            payload["capabilities"]["chrome"]["composer"]["command_menu"],
            {
                "path_group_label": "Files",
                "command_group_fallback_label": "Command",
                "path_empty_text": "No files found",
                "command_empty_text": "No commands found",
                "default_empty_text": "No matches",
                "path_aria_label": "File context suggestions",
                "command_aria_label": "Slash command suggestions",
                "path_item_kind_label": "file",
                "command_item_kind_label": "command",
            },
        )
        self.assertEqual(
            payload["capabilities"]["chrome"]["interaction"]["approve_once_label"],
            "Approve once",
        )
        self.assertEqual(
            payload["capabilities"]["chrome"]["surface_panel"]["aria_label"],
            "Surface panel",
        )
        thread_actions = payload["capabilities"]["thread_lifecycle"]["actions"]
        self.assertEqual(thread_actions[0]["prompt_title"], "Rename thread")
        self.assertEqual(thread_actions[0]["empty_body"], "Thread title cannot be empty.")
        self.assertEqual(thread_actions[1]["prompt_title"], "Fork thread title")
        self.assertEqual(thread_actions[2]["confirm_title"], "Archive this thread?")
        self.assertEqual(thread_actions[2]["success_title"], "Thread archived")
        self.assertEqual(
            payload["capabilities"]["home"]["workspace"]["inactive_label"],
            "No workspace",
        )
        self.assertEqual(
            payload["capabilities"]["home"]["threads"]["empty_title"],
            "No threads yet",
        )
        self.assertEqual(
            payload["capabilities"]["source_control"],
            {
                "enabled": True,
                "vcs": ["git"],
                "read_only": True,
                "remote_providers": False,
                "network": False,
                "checkpoints": False,
                "requires_active_workspace": True,
                "chrome": {
                    "title": "Source Control",
                    "status_unavailable_notice": "Source control unavailable.",
                    "diff_unavailable_notice": "Diff unavailable",
                    "loading_message": "Loading changes...",
                    "git_unavailable_message": ("Git runtime is not available for this workspace."),
                    "not_repository_message": ("The active workspace is not a Git repository."),
                    "clean_message": "No local changes.",
                    "no_branch_label": "No branch",
                    "runtime_git_label": "git",
                    "missing_runtime_label": "missing",
                    "refresh_label": "Refresh",
                    "count_labels": {
                        "files": "files",
                        "staged": "staged",
                        "changed": "changed",
                        "untracked": "untracked",
                    },
                    "group_labels": {
                        "staged": "Staged",
                        "unstaged": "Changes",
                        "untracked": "Untracked",
                        "conflicted": "Conflicts",
                        "fallback": "Changes",
                    },
                    "provider_labels": {
                        "azure": "Azure Repos",
                        "bitbucket": "Bitbucket",
                        "gitea": "Gitea",
                        "github": "GitHub",
                        "gitlab": "GitLab",
                        "local": "Local Git",
                        "fallback": "Local Git",
                    },
                    "file_status_labels": {
                        "added": "A",
                        "copied": "C",
                        "deleted": "D",
                        "modified": "M",
                        "renamed": "R",
                        "typechange": "T",
                        "untracked": "U",
                        "conflicted": "C",
                    },
                    "branch_toolbar": {
                        "default_workspace_label": "Workspace",
                        "loading_label": "Checking Git...",
                        "error_label": "Git status unavailable",
                        "git_unavailable_label": "Git unavailable",
                        "not_repository_label": "No repository",
                        "unknown_ref_label": "Unknown ref",
                        "detached_prefix": "detached",
                        "clean_label": "Clean",
                        "change_singular": "change",
                        "change_plural": "changes",
                        "conflict_singular": "conflict",
                        "conflict_plural": "conflicts",
                        "current_checkout_label": "Current checkout",
                        "current_checkout_description": ("Run in the active workspace checkout."),
                        "git_unavailable_reason": (
                            "Git is unavailable in this offline bundle or workspace."
                        ),
                        "not_repository_reason": ("This workspace is not a Git repository."),
                        "error_reason_fallback": "Git status is unavailable.",
                        "read_only_action_title": (
                            "This action is read-only in the current GUI shell."
                        ),
                        "worktree_action_label": "Worktree",
                        "branch_action_label": "Branch",
                        "refresh_label": "Refresh",
                        "refresh_title": "Refresh local Git status",
                        "metadata_separator": " / ",
                    },
                },
            },
        )
        terminal_capability = payload["capabilities"]["terminal"]
        self.assertEqual(terminal_capability["enabled"], True)
        self.assertEqual(terminal_capability["pty"], False)
        self.assertEqual(terminal_capability["resize"], False)
        self.assertEqual(terminal_capability["history_persistent"], False)
        self.assertEqual(terminal_capability["max_buffer_bytes"], 131072)
        self.assertEqual(terminal_capability["chrome"]["title_prefix"], "Terminal")
        self.assertEqual(
            terminal_capability["chrome"]["session_required_notice"],
            "Open a session before using the terminal.",
        )
        self.assertEqual(terminal_capability["chrome"]["new_label"], "New")
        self.assertEqual(
            terminal_capability["chrome"]["command_placeholder"],
            "Type a command",
        )
        preview_capability = payload["capabilities"]["preview"]
        self.assertEqual(preview_capability["enabled"], True)
        self.assertEqual(preview_capability["local_servers"][0]["label"], "Vite dev server")
        self.assertEqual(preview_capability["chrome"]["refresh_label"], "Refresh")
        self.assertEqual(
            preview_capability["chrome"]["session_required_notice"],
            "Open a session before using preview.",
        )
        self.assertEqual(
            preview_capability["chrome"]["empty_title"],
            "No preview open",
        )
        bottom_drawer_surfaces = [
            item["id"] for item in payload["capabilities"]["surfaces"]["bottom_drawer"]
        ]
        self.assertIn("terminal", bottom_drawer_surfaces)
        self.assertTrue(payload["settings"]["confirm_workspace_switch"])
        self.assertIn("host", payload["diagnostics"])
        self.assertIn("runtime", payload["diagnostics"])
        self.assertIn("renderer", payload["diagnostics"])
        self.assertIn("workspace_registry", payload["diagnostics"])
        self.assertIn("active_core", payload["diagnostics"])
        self.assertEqual(payload["diagnostics"]["active_core"]["present"], False)
        self.assertIs(host.current_core(), None)
        self.assertEqual(frontend.messages, [])

    def test_bootstrap_without_workspace_projects_selected_agent_application(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            created = []
            service, host, frontend = self._service(
                registry,
                created,
                agent_capabilities=agent_application_capability_payload("embedagent.python"),
            )

            payload = service.bootstrap()

        self.assertEqual(created, [])
        self.assertIs(host.current_core(), None)
        self.assertEqual(frontend.messages, [])
        self.assertEqual(payload["has_active_workspace"], False)
        self.assertEqual(
            payload["capabilities"]["agentApplication"]["applicationId"],
            "embedagent.python",
        )
        self.assertEqual(
            payload["capabilities"]["agentApplications"][0]["applicationId"],
            "embedagent.default_c_cpp",
        )
        self.assertEqual(
            payload["capabilities"]["emptyState"]["scenario_label"],
            "Python workspace",
        )

    def test_bootstrap_uses_injected_app_shell_spec(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            service, _host, _frontend = self._service(
                registry,
                [],
                shell_spec=AppShellSpec(
                    app_commands=(
                        {
                            "id": "app.settings",
                            "label": "Preferences",
                            "group": "app",
                        },
                    ),
                    workspace_commands=(
                        {
                            "id": "workspace.open",
                            "label": "Open Project",
                            "group": "workspace",
                        },
                    ),
                    workbench_commands=(
                        {
                            "id": "palette.open",
                            "label": "Launch",
                            "group": "view",
                        },
                    ),
                    command_palette_labels={
                        "root_title": "Launcher",
                        "commands_section": "Actions",
                    },
                    chrome={
                        "brand_subtitle": "Injected shell",
                        "composer": {"placeholder": "Ask"},
                    },
                    surface_chrome={
                        "empty_title": "Open view",
                        "close_all_action_label": "Close views",
                        "bottom_drawer_aria_label": "Output",
                    },
                    right_panel_surfaces=(
                        {
                            "id": "settings",
                            "title": "Settings",
                            "launcher_order": 10,
                        },
                    ),
                    bottom_drawer_surfaces=(),
                    keybindings=(
                        {
                            "key": "mod+,",
                            "command_id": "app.settings",
                            "when": "always",
                        },
                    ),
                    source_control={"enabled": False},
                    terminal={"enabled": False},
                    preview={"enabled": False},
                    thread_lifecycle_actions=(),
                    home={
                        "workspace": {
                            "section_title": "Projects",
                            "open_label": "Open Project",
                        },
                        "threads": {
                            "section_title": "Runs",
                            "new_label": "Start",
                        },
                    },
                ),
            )

            payload = service.bootstrap()

        self.assertEqual(
            [item["id"] for item in payload["capabilities"]["app_commands"]],
            ["app.settings"],
        )
        self.assertEqual(
            [item["id"] for item in payload["capabilities"]["workspace_commands"]],
            ["workspace.open"],
        )
        self.assertEqual(
            [item["id"] for item in payload["capabilities"]["workbench_commands"]],
            ["palette.open"],
        )
        self.assertEqual(
            [item["id"] for item in payload["capabilities"]["surfaces"]["right_panel"]],
            ["settings"],
        )
        self.assertEqual(payload["capabilities"]["surfaces"]["bottom_drawer"], [])
        self.assertEqual(
            payload["capabilities"]["surfaces"]["chrome"],
            {
                "empty_title": "Open view",
                "close_all_action_label": "Close views",
                "bottom_drawer_aria_label": "Output",
            },
        )
        self.assertEqual(
            payload["capabilities"]["keybindings"],
            [{"key": "mod+,", "command_id": "app.settings", "when": "always"}],
        )
        self.assertEqual(payload["capabilities"]["source_control"], {"enabled": False})
        self.assertEqual(payload["capabilities"]["preview"], {"enabled": False})
        self.assertEqual(
            payload["capabilities"]["command_palette"],
            {
                "groups": [],
                "labels": {
                    "root_title": "Launcher",
                    "commands_section": "Actions",
                },
            },
        )
        self.assertEqual(
            payload["capabilities"]["chrome"],
            {
                "brand_subtitle": "Injected shell",
                "composer": {"placeholder": "Ask"},
            },
        )
        self.assertEqual(payload["capabilities"]["thread_lifecycle"], {"actions": []})
        self.assertEqual(
            payload["capabilities"]["home"],
            {
                "workspace": {
                    "section_title": "Projects",
                    "open_label": "Open Project",
                },
                "threads": {
                    "section_title": "Runs",
                    "new_label": "Start",
                },
            },
        )

    def test_open_workspace_returns_app_shell_payload_and_binds_core(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            workspace = os.path.join(root, "project-a")
            os.mkdir(workspace)
            created = []
            service, host, frontend = self._service(registry, created)

            payload = service.open_workspace_path(workspace)

        self.assertEqual(payload["active_workspace"]["path"], os.path.realpath(workspace))
        self.assertEqual(payload["has_active_workspace"], True)
        self.assertEqual(
            payload["capabilities"]["agentApplication"]["applicationId"],
            "tests.python",
        )
        self.assertEqual(
            payload["capabilities"]["agentApplications"][0]["profileId"],
            "tests.python.profile",
        )
        self.assertEqual(
            payload["capabilities"]["emptyState"]["scenario_label"],
            "Python workspace",
        )
        self.assertEqual(payload["diagnostics"]["active_core"]["present"], True)
        self.assertEqual(payload["diagnostics"]["workspace_registry"]["count"], 1)
        self.assertEqual(len(created), 1)
        self.assertIs(created[0].frontend, frontend)
        self.assertIs(host.current_core(), created[0])
        self.assertEqual(frontend.messages[-1]["type"], "workspace_changed")

    def test_removed_workspace_payload_keeps_shell_fields(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            workspace = os.path.join(root, "project-a")
            os.mkdir(workspace)
            created = []
            service, host, _frontend = self._service(registry, created)
            opened = service.open_workspace_path(workspace)

            payload = service.remove_workspace(opened["active_workspace"]["id"])

        self.assertEqual(payload["removed"], True)
        self.assertEqual(payload["workspaces"], [])
        self.assertIsNone(payload["active_workspace"])
        self.assertEqual(payload["has_active_workspace"], False)
        self.assertEqual(payload["diagnostics"]["active_core"]["present"], False)
        self.assertIn("app", payload)
        self.assertIn("capabilities", payload)
        self.assertIn("settings", payload)
        self.assertEqual(created[0].shutdown_calls, 1)
        self.assertIs(host.current_core(), None)

    def test_bootstrap_excludes_session_history_and_secret_fields(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            created = []
            service, _host, _frontend = self._service(
                registry,
                created,
                host_diagnostics={
                    "host": {
                        "platform": "win32",
                        "api_key": "sk-secret",
                        "nested": {"token": "secret-token", "safe": "ok"},
                    },
                    "runtime": {"authorization": "Bearer abc", "runtime_source": "bundle"},
                    "renderer": {"prompt": "hidden prompt", "renderer": "edgechromium"},
                    "transcript": {"messages": ["do not serialize"]},
                    "tool_output": "hidden tool output",
                },
            )

            payload = service.bootstrap()
            serialized = json.dumps(payload, sort_keys=True)

        self.assertNotIn("api_key", serialized)
        self.assertNotIn("sk-secret", serialized)
        self.assertNotIn("token", serialized)
        self.assertNotIn("secret-token", serialized)
        self.assertNotIn("authorization", serialized)
        self.assertNotIn("Bearer abc", serialized)
        self.assertNotIn("hidden prompt", serialized)
        self.assertNotIn("transcript", serialized)
        self.assertNotIn("tool_output", serialized)
        self.assertIn('"safe": "ok"', serialized)
        self.assertEqual(created, [])


if __name__ == "__main__":
    unittest.main()
