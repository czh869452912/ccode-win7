from __future__ import unicode_literals

import ast
import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "standalone_agent.py"


def test_standalone_example_uses_only_core_root_imports():
    source = EXAMPLE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(EXAMPLE))

    core_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("embedagent_core"):
            core_imports.append(node.module)

    assert core_imports == ["embedagent_core"]
    for forbidden in (
        "embedagent_host",
        "embedagent_protocol",
        "embedagent_composition",
        "embedagent_workflow_cpp",
        "from embedagent ",
    ):
        assert forbidden not in source


def test_standalone_example_implements_explicit_path_resolver():
    namespace = runpy.run_path(str(EXAMPLE), run_name="standalone_example_test")
    runtime = namespace["StandaloneToolRuntime"]()

    resolver = runtime.path_resolver()

    with pytest.raises(RuntimeError, match="does not expose workspace paths"):
        resolver.resolve_path("source.c")


def test_standalone_example_suspends_and_resumes_same_session():
    completed = subprocess.run(
        [sys.executable, "-I", str(EXAMPLE)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "final_text": "done",
        "interaction_kind": "user_input",
        "session_id": "standalone-example",
        "termination_reason": "completed",
        "waiting_reason": "user_input_wait",
    }
