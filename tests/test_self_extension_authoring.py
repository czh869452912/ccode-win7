from __future__ import annotations

import json


def test_authors_skill_prompt_recipe_and_disabled_extension(tmp_path):
    from embedagent.self_extension_authoring import (
        AuthoringRequest,
        SelfExtensionAuthoringService,
    )

    service = SelfExtensionAuthoringService(str(tmp_path))

    skill = service.author(
        AuthoringRequest(kind="skill", name="Code Review", summary="Review local C changes.")
    )
    prompt = service.author(
        AuthoringRequest(kind="prompt", name="Triage Prompt", body="Classify the issue.")
    )
    recipe = service.author(
        AuthoringRequest(
            kind="recipe",
            name="Local Verify",
            command="cmd /c echo verify-ok",
            recipe_action="test",
        )
    )
    extension = service.author(
        AuthoringRequest(kind="extension", name="Project Echo", summary="Read-only echo demo.")
    )

    assert skill.success is True
    assert prompt.success is True
    assert recipe.success is True
    assert extension.success is True
    assert (tmp_path / ".embedagent" / "skills" / "code-review.md").is_file()
    assert (tmp_path / ".embedagent" / "prompts" / "triage-prompt.md").is_file()
    assert (tmp_path / ".embedagent" / "recipes" / "local-verify.json").is_file()
    manifest_path = tmp_path / ".embedagent" / "extensions" / "project-echo" / "extension.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["id"] == "project_echo"
    assert manifest["enabled"] is False
    assert manifest["permissions"] == ["read"]


def test_authoring_rejects_empty_names_invalid_permissions_and_no_overwrite(tmp_path):
    from embedagent.self_extension_authoring import (
        AuthoringRequest,
        SelfExtensionAuthoringService,
    )

    service = SelfExtensionAuthoringService(str(tmp_path))

    empty = service.author(AuthoringRequest(kind="skill", name=""))
    invalid_permission = service.author(
        AuthoringRequest(kind="extension", name="Bad Permission", permissions=["network"])
    )
    first = service.author(AuthoringRequest(kind="skill", name="Duplicate"))
    second = service.author(AuthoringRequest(kind="skill", name="Duplicate"))
    overwrite = service.author(AuthoringRequest(kind="skill", name="Duplicate", overwrite=True))

    assert empty.success is False
    assert "required" in empty.diagnostics[0]["error"]
    assert invalid_permission.success is False
    assert "unsupported permission" in invalid_permission.diagnostics[0]["error"]
    assert first.success is True
    assert second.success is False
    assert second.files[0].status == "skipped"
    assert overwrite.success is True
    assert overwrite.files[0].status == "written"
