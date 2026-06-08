from __future__ import annotations


def test_disabled_manifest_is_discovered_but_not_imported(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "sample"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "sample_extension", "enabled": false, "permissions": ["read"]}',
        encoding="utf-8",
    )
    (root / "extension.py").write_text(
        "raise RuntimeError('should not import')",
        encoding="utf-8",
    )

    from embedagent.project_extensions import load_project_extensions

    payload = load_project_extensions(str(tmp_path))

    assert payload["counts"]["discovered"] == 1
    assert payload["counts"]["disabled"] == 1
    assert payload["counts"]["loaded"] == 0
    assert payload["extensions"][0]["status"] == "disabled"
    assert payload["loaded_extensions"] == []
    assert payload["diagnostics"] == []


def test_enabled_manifest_requires_permissions(tmp_path):
    root = tmp_path / ".embedagent" / "extensions" / "sample"
    root.mkdir(parents=True)
    (root / "extension.json").write_text(
        '{"id": "sample_extension", "enabled": true}',
        encoding="utf-8",
    )

    from embedagent.project_extensions import load_project_extensions

    payload = load_project_extensions(str(tmp_path))

    assert payload["counts"]["failed"] == 1
    assert payload["extensions"][0]["status"] == "failed"
    assert "permissions" in payload["diagnostics"][0]["error"]
