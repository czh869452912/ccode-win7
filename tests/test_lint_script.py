from __future__ import annotations

import sys
from importlib import util
from pathlib import Path

_LINT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "lint.py"
_LINT_SPEC = util.spec_from_file_location("embedagent_lint_script", str(_LINT_PATH))
assert _LINT_SPEC is not None
assert _LINT_SPEC.loader is not None
lint = util.module_from_spec(_LINT_SPEC)
_LINT_SPEC.loader.exec_module(lint)


def test_lint_script_builds_default_check_commands(monkeypatch):
    calls = []
    monkeypatch.setattr(lint.subprocess, "call", lambda command: calls.append(command) or 0)

    assert lint.main(()) == 0

    assert calls == [
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "src/",
            "packages/embedagent-core/src/",
            "packages/embedagent-protocol/src/",
            "packages/embedagent-host/src/",
            "tests/",
            "scripts/lint.py",
        ],
        [
            sys.executable,
            "-m",
            "black",
            "--check",
            "src/",
            "packages/embedagent-core/src/",
            "packages/embedagent-protocol/src/",
            "packages/embedagent-host/src/",
            "tests/",
            "scripts/lint.py",
        ],
    ]


def test_lint_script_builds_fix_commands_for_explicit_targets(monkeypatch):
    calls = []
    monkeypatch.setattr(lint.subprocess, "call", lambda command: calls.append(command) or 0)

    assert (
        lint.main(("--fix", "packages/embedagent-host/src/embedagent_host/runtime/skills.py")) == 0
    )

    assert calls == [
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--fix",
            "packages/embedagent-host/src/embedagent_host/runtime/skills.py",
        ],
        [
            sys.executable,
            "-m",
            "black",
            "packages/embedagent-host/src/embedagent_host/runtime/skills.py",
        ],
    ]


def test_lint_script_stops_after_first_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(lint.subprocess, "call", lambda command: calls.append(command) or 7)

    assert lint.main(("tests/test_lint_script.py",)) == 7

    assert calls == [
        [sys.executable, "-m", "ruff", "check", "tests/test_lint_script.py"],
    ]
