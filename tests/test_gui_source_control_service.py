import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.backend.source_control_service import SourceControlService


class FakeRunner(object):
    def __init__(self, responses=None):
        self.calls = []
        self.responses = list(responses or [])

    def __call__(self, command, cwd, timeout_sec, max_output_bytes, env):
        self.calls.append((list(command), cwd, timeout_sec, max_output_bytes, dict(env or {})))
        if self.responses:
            return dict(self.responses.pop(0))
        return {"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False, "truncated": False}


class SourceControlServiceTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="embedagent-source-control-")
        self.addCleanup(lambda: shutil.rmtree(self.workspace, ignore_errors=True))

    def service(self, responses):
        return SourceControlService(
            workspace_root=self.workspace,
            git_executable="git.exe",
            command_runner=FakeRunner(responses),
        )

    def test_git_unavailable_returns_safe_status(self):
        service = SourceControlService(
            workspace_root=self.workspace,
            git_executable="",
            command_runner=FakeRunner(),
        )

        status = service.status()

        self.assertEqual(status["git_available"], False)
        self.assertEqual(status["is_repo"], False)
        self.assertEqual(status["counts"]["total"], 0)
        self.assertEqual(status["files"], [])

    def test_not_a_repo_is_not_fatal(self):
        service = self.service(
            [
                {
                    "exit_code": 128,
                    "stdout": "",
                    "stderr": "fatal: not a git repository",
                    "timed_out": False,
                    "truncated": False,
                },
            ]
        )

        status = service.status()

        self.assertEqual(status["git_available"], True)
        self.assertEqual(status["is_repo"], False)
        self.assertEqual(status["diagnostics"]["warnings"], ["not_a_repo"])

    def test_status_parses_changed_files_and_counts(self):
        service = self.service(
            [
                {
                    "exit_code": 0,
                    "stdout": (
                        "## main...origin/main\n"
                        " M src/main.c\n"
                        "A  include/api.h\n"
                        "?? notes.txt\n"
                        "UU conflict.c\n"
                    ),
                    "stderr": "",
                    "timed_out": False,
                    "truncated": False,
                },
                {
                    "exit_code": 0,
                    "stdout": "abcdef1\n",
                    "stderr": "",
                    "timed_out": False,
                    "truncated": False,
                },
                {
                    "exit_code": 0,
                    "stdout": "https://github.com/example/demo.git\n",
                    "stderr": "",
                    "timed_out": False,
                    "truncated": False,
                },
                {
                    "exit_code": 0,
                    "stdout": "12\t3\tsrc/main.c\n5\t0\tinclude/api.h\n-\t-\tnotes.txt\n",
                    "stderr": "",
                    "timed_out": False,
                    "truncated": False,
                },
            ]
        )

        status = service.status()

        self.assertEqual(status["is_repo"], True)
        self.assertEqual(status["branch"], "main")
        self.assertEqual(status["head"], "abcdef1")
        self.assertEqual(status["provider"]["kind"], "github")
        self.assertEqual(status["counts"]["unstaged"], 1)
        self.assertEqual(status["counts"]["staged"], 1)
        self.assertEqual(status["counts"]["untracked"], 1)
        self.assertEqual(status["counts"]["conflicted"], 1)
        self.assertEqual(status["counts"]["total"], 4)
        self.assertEqual(status["files"][0]["path"], "src/main.c")
        self.assertEqual(status["files"][0]["group"], "unstaged")
        self.assertEqual(status["files"][0]["insertions"], 12)
        self.assertEqual(status["files"][0]["deletions"], 3)

    def test_diff_rejects_workspace_escape_and_invalid_scope(self):
        service = self.service([])

        with self.assertRaises(ValueError) as raised:
            service.diff("../outside.c")
        self.assertEqual(str(raised.exception), "path_outside_workspace")

        with self.assertRaises(ValueError) as raised:
            service.diff("src/main.c", scope="remote")
        self.assertEqual(str(raised.exception), "invalid_diff_scope")

    def test_diff_returns_payload(self):
        service = self.service(
            [
                {
                    "exit_code": 0,
                    "stdout": (
                        "diff --git a/src/main.c b/src/main.c\n"
                        "--- a/src/main.c\n"
                        "+++ b/src/main.c\n"
                        "@@ -1 +1 @@\n"
                        "-old\n"
                        "+new\n"
                    ),
                    "stderr": "",
                    "timed_out": False,
                    "truncated": False,
                },
            ]
        )

        payload = service.diff("src/main.c", scope="unstaged")

        self.assertEqual(payload["available"], True)
        self.assertEqual(payload["path"], "src/main.c")
        self.assertEqual(payload["scope"], "unstaged")
        self.assertEqual(payload["file_count"], 1)
        self.assertEqual(payload["line_count"], 6)
        self.assertIn("diff --git", payload["diff"])


if __name__ == "__main__":
    unittest.main()
