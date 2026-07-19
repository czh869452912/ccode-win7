import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_verify_declares_all_local_release_gates():
    script = (ROOT / "scripts" / "package-lib.ps1").read_text(encoding="utf-8")

    for marker in (
        "gui_headless_smoke",
        "cpp_smoke",
        "zip_extraction",
        "identity_reproducibility",
        "RequireComplete",
    ):
        assert marker in script


def test_local_release_status_is_target_ready_only():
    script = (ROOT / "scripts" / "package-lib.ps1").read_text(encoding="utf-8")

    assert "final_status = 'TARGET_READY'" in script
    assert "release_state = 'TARGET_READY'" in script
    assert "'TARGET_READY' { return 0 }" in script
    assert "'ACCEPTED'" not in script


def test_reproducibility_fixture_declares_operational_fields():
    fixture = ROOT / "tests" / "fixtures" / "packaging" / "reproducibility-config.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))

    assert payload["first_output_root"] != payload["second_output_root"]
    assert "generated_at" in payload["operational_fields"]
    assert "duration_ms" in payload["operational_fields"]
