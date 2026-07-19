import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from embedagent.frontend.gui import launcher


def test_startup_report_is_atomic_and_records_safe_events(tmp_path):
    path = tmp_path / "nested" / "startup.json"

    launcher._write_startup_report(
        str(path),
        ["dependencies_checked", "backend_constructed"],
        status="ready",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["status"] == "ready"
    assert payload["events"] == ["dependencies_checked", "backend_constructed"]
    assert not (path.parent / "startup.json.tmp").exists()


def test_startup_report_failure_contains_only_exception_metadata(tmp_path):
    path = tmp_path / "startup.json"

    launcher._write_startup_report(
        str(path),
        ["dependencies_checked"],
        status="failed",
        error=ValueError("safe failure"),
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["error"] == {"type": "ValueError", "message": "safe failure"}
    text = json.dumps(payload)
    assert "api_key" not in text
    assert "prompt" not in text
    assert "raw_output" not in text


def test_launcher_parser_exposes_startup_report():
    args = launcher.build_parser().parse_args(["--startup-report", "startup.json"])

    assert args.startup_report == "startup.json"
