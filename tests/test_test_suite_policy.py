from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "test-suite.py"


def load_test_suite_script():
    spec = importlib.util.spec_from_file_location("embedagent_test_suite_policy", str(SCRIPT_PATH))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_test_modules_do_not_spawn_nested_full_pytest():
    suite = load_test_suite_script()

    assert suite.nested_full_pytest_violations(ROOT / "tests") == ()
