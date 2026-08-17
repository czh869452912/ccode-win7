from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_active_architecture_docs_do_not_claim_fixed_six_wheel_runtime():
    paths = (
        ROOT / "AGENTS.md",
        ROOT / "docs" / "overall-solution-architecture.md",
        ROOT / "docs" / "product" / "packaging-and-deployment.md",
    )
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "exactly six Python distributions" not in text
    assert "PORTABLE_PROJECT_DISTRIBUTIONS" not in text


def test_plugin_authoring_doc_names_registration_contract():
    text = (ROOT / "docs" / "guides" / "application-plugin-authoring.md").read_text(
        encoding="utf-8"
    )
    assert "application_id" in text
    assert "registration_entry" in text
    assert "dispose" in text
