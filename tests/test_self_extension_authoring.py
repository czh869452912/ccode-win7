from __future__ import annotations

import json


def test_authors_skill_prompt_recipe_and_disabled_extension(tmp_path):
    from embedagent.local_resources import discover_local_resources
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
    skill_path = tmp_path / ".embedagent" / "skills" / "code-review.md"
    assert skill_path.is_file()
    skill_text = skill_path.read_text(encoding="utf-8")
    assert skill_text.startswith("---\n")
    assert "name: code-review\n" in skill_text
    assert "description: Review local C changes.\n" in skill_text
    assert "disable-model-invocation: false\n" in skill_text
    assert (tmp_path / ".embedagent" / "prompts" / "triage-prompt.md").is_file()
    recipe_path = tmp_path / ".embedagent" / "recipes" / "local-verify.json"
    assert recipe_path.is_file()
    recipe_payload = json.loads(recipe_path.read_text(encoding="utf-8"))
    assert "tool_name" not in recipe_payload
    assert recipe_payload["recipe_action"] == "test"
    manifest_path = tmp_path / ".embedagent" / "extensions" / "project-echo" / "extension.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["id"] == "project_echo"
    assert manifest["enabled"] is False
    assert manifest["permissions"] == ["read"]
    resources = discover_local_resources(str(tmp_path))
    assert resources["skills"][0]["name"] == "code-review"
    assert resources["skills"][0]["description"] == "Review local C changes."
    assert resources["skills"][0]["prompt_visible"] is True


def test_authoring_rejects_empty_names_invalid_permissions_and_no_overwrite(tmp_path):
    from embedagent.self_extension_authoring import (
        AuthoringRequest,
        SelfExtensionAuthoringService,
    )

    service = SelfExtensionAuthoringService(str(tmp_path))

    empty = service.author(AuthoringRequest(kind="skill", name=""))
    invalid_permission = service.author(
        AuthoringRequest(kind="extension", name="Bad Permission", permissions=["remote_install"])
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


def test_authoring_accepts_network_and_telemetry_extension_permissions(tmp_path):
    from embedagent.self_extension_authoring import (
        AuthoringRequest,
        SelfExtensionAuthoringService,
    )

    result = SelfExtensionAuthoringService(str(tmp_path)).author(
        AuthoringRequest(
            kind="extension",
            name="Enterprise Bridge",
            permissions=["network", "telemetry"],
        )
    )

    manifest_path = tmp_path / ".embedagent" / "extensions" / "enterprise-bridge" / "extension.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert result.success is True
    assert manifest["permissions"] == ["network", "telemetry"]


def test_generated_recipe_updates_resource_snapshot_after_runtime_reload(tmp_path):
    from embedagent.self_extension_authoring import (
        AuthoringRequest,
        SelfExtensionAuthoringService,
    )
    from embedagent.tools import ToolRuntime

    runtime = ToolRuntime(str(tmp_path))
    before_resources = runtime.local_resources()
    result = SelfExtensionAuthoringService(str(tmp_path)).author(
        AuthoringRequest(
            kind="recipe",
            name="Author Verify",
            command="cmd /c echo author-verify",
            recipe_action="test",
        )
    )
    after_write_resources = runtime.local_resources()
    reloaded = runtime.reload_resources(reason="authoring-test")
    after_reload_resources = runtime.local_resources()
    recipes = runtime.workspace_recipes()
    authored_recipe = [
        item for item in recipes["items"] if item.get("id") == "local.author_verify"
    ][0]

    assert result.success is True
    assert before_resources["counts"]["recipes"] == 0
    assert after_write_resources["counts"]["recipes"] == 0
    assert reloaded["counts"]["recipes"] == 1
    assert after_reload_resources["counts"]["recipes"] == 1
    assert authored_recipe["tool_name"] == "run_recipe"


def test_generated_extension_is_disabled_and_not_imported(tmp_path):
    from embedagent.project_extensions import load_project_extensions
    from embedagent.self_extension_authoring import (
        AuthoringRequest,
        SelfExtensionAuthoringService,
    )

    result = SelfExtensionAuthoringService(str(tmp_path)).author(
        AuthoringRequest(kind="extension", name="Safe Extension", summary="Safe by default.")
    )
    extension_py = tmp_path / ".embedagent" / "extensions" / "safe-extension" / "extension.py"
    extension_py.write_text(
        "raise RuntimeError('should not import while disabled')\n",
        encoding="utf-8",
    )

    payload = load_project_extensions(str(tmp_path))

    assert result.success is True
    assert payload["counts"]["disabled"] == 1
    assert payload["counts"]["loaded"] == 0
    assert payload["diagnostics"] == []


def test_generated_extension_validation_recipe_uses_managed_python_command(tmp_path):
    from embedagent.self_extension_authoring import (
        AuthoringRequest,
        SelfExtensionAuthoringService,
    )

    result = SelfExtensionAuthoringService(str(tmp_path)).author(
        AuthoringRequest(kind="extension", name="Compile Check", summary="Validate code.")
    )
    recipe_path = (
        tmp_path / ".embedagent" / "extensions" / "compile-check" / "recipes" / "validate.json"
    )
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))

    assert result.success is True
    assert "tool_name" not in recipe
    assert recipe["recipe_action"] == "test"
    assert recipe["command"].startswith("python -m py_compile ")
