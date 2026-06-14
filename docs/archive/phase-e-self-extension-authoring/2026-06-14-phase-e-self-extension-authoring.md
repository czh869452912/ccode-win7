# Phase E Self-Extension Authoring Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a safe local authoring loop for skills, prompts, recipes, and disabled-by-default project extension skeletons.

**Architecture:** Add a small `SelfExtensionAuthoringService` that writes only workspace-bound `.embedagent` artifacts and returns diagnostics plus next actions. Expose it through a workflow-neutral `author_local_capability` runtime tool with `workspace_write` permission, while preserving the existing separation between file-resource reload and executable project-extension loading.

**Tech Stack:** Python 3.8 standard library, existing `ToolRuntime`, `ToolDefinition`, `Observation`, local resource discovery, project extension loader, pytest, ruff, black.

---

## File Structure

- Create `src/embedagent/self_extension_authoring.py`
  - Owns request/result dataclasses, slug/path validation, artifact templates, write semantics, and next-action text.
- Create `src/embedagent/tools/authoring_ops.py`
  - Exposes `author_local_capability` as a `ToolDefinition`.
- Modify `src/embedagent/tools/runtime.py`
  - Imports/registers `authoring_ops`.
  - Adds catalog metadata for `author_local_capability`.
- Modify `src/embedagent/modes.py`
  - Adds `author_local_capability` to `build` and `debug` only.
- Add `tests/test_self_extension_authoring.py`
  - Unit tests for the service and safety rules.
- Modify `tests/test_tools_package.py`
  - Catalog/schema tests for the new tool.
- Modify `tests/test_permissions.py`
  - Permission category coverage if existing assertions need explicit catalog lookup.
- Modify docs during closeout:
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`

---

## Task E-A: Authoring Service

**Files:**
- Create: `src/embedagent/self_extension_authoring.py`
- Create: `tests/test_self_extension_authoring.py`

- [ ] **Step 1: Write failing tests for skill, prompt, recipe, and extension generation**

Add `tests/test_self_extension_authoring.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_self_extension_authoring.py::test_authors_skill_prompt_recipe_and_disabled_extension -q
```

Expected: FAIL because `embedagent.self_extension_authoring` does not exist.

- [ ] **Step 3: Implement dataclasses and artifact writers**

Create `src/embedagent/self_extension_authoring.py`:

```python
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

_VALID_KIND = set(["skill", "prompt", "recipe", "extension"])
_VALID_PERMISSION = set(["read", "workspace_write", "shell_exec", "toolchain_exec", "git_write"])


@dataclass
class AuthoringRequest:
    kind: str
    name: str
    summary: str = ""
    body: str = ""
    command: str = ""
    recipe_action: str = "custom"
    permissions: List[str] = field(default_factory=lambda: ["read"])
    overwrite: bool = False


@dataclass
class AuthoredFile:
    path: str
    kind: str
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return {"path": self.path, "kind": self.kind, "status": self.status}


@dataclass
class AuthoringResult:
    success: bool
    kind: str
    name: str
    slug: str
    files: List[AuthoredFile] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    next_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "kind": self.kind,
            "name": self.name,
            "slug": self.slug,
            "files": [item.to_dict() for item in self.files],
            "diagnostics": list(self.diagnostics),
            "next_actions": list(self.next_actions),
        }


class SelfExtensionAuthoringService(object):
    def __init__(self, workspace: str) -> None:
        self.workspace = os.path.realpath(workspace)

    def author(self, request: AuthoringRequest) -> AuthoringResult:
        kind = str(request.kind or "").strip().lower()
        name = str(request.name or "").strip()
        slug = _slugify(name)
        diagnostics = []  # type: List[Dict[str, Any]]
        if kind not in _VALID_KIND:
            return _failed(kind, name, slug, "unsupported authoring kind: %s" % (kind or "<empty>"))
        if not slug:
            return _failed(kind, name, slug, "capability name is required")
        invalid_permissions = [
            str(item or "").strip() for item in request.permissions if str(item or "").strip() not in _VALID_PERMISSION
        ]
        if invalid_permissions:
            return _failed(kind, name, slug, "unsupported permission: %s" % invalid_permissions[0])
        if kind == "skill":
            files = self._write_skill(slug, name, request, diagnostics)
        elif kind == "prompt":
            files = self._write_prompt(slug, name, request, diagnostics)
        elif kind == "recipe":
            files = self._write_recipe(slug, name, request, diagnostics)
        else:
            files = self._write_extension(slug, name, request, diagnostics)
        return AuthoringResult(
            success=len(diagnostics) == 0,
            kind=kind,
            name=name,
            slug=slug,
            files=files,
            diagnostics=diagnostics,
            next_actions=_next_actions(kind),
        )

    def _write_skill(self, slug: str, name: str, request: AuthoringRequest, diagnostics: List[Dict[str, Any]]) -> List[AuthoredFile]:
        content = "# %s\n\n## Purpose\n\n%s\n\n## When To Use\n\nDescribe when this local skill should guide the agent.\n\n## Inputs\n\n- Workspace context\n- User request\n\n## Output Contract\n\nState the expected output clearly.\n\n## Validation\n\nReload local resources after editing this file.\n" % (
            name,
            request.summary or "Describe the local skill purpose.",
        )
        return [self._write_file(".embedagent/skills/%s.md" % slug, content, "skill", request.overwrite, diagnostics)]

    def _write_prompt(self, slug: str, name: str, request: AuthoringRequest, diagnostics: List[Dict[str, Any]]) -> List[AuthoredFile]:
        content = "# %s\n\n## Intended Use\n\n%s\n\n## Prompt\n\n%s\n\n## Safety Notes\n\nKeep this prompt local to the workspace and reload resources after editing.\n" % (
            name,
            request.summary or "Describe when this prompt should be used.",
            request.body or "Write the prompt body here.",
        )
        return [self._write_file(".embedagent/prompts/%s.md" % slug, content, "prompt", request.overwrite, diagnostics)]

    def _write_recipe(self, slug: str, name: str, request: AuthoringRequest, diagnostics: List[Dict[str, Any]]) -> List[AuthoredFile]:
        if not str(request.command or "").strip():
            diagnostics.append({"kind": "recipe", "error": "recipe command is required"})
            return []
        payload = {
            "id": "local.%s" % slug.replace("-", "_"),
            "tool_name": "run_recipe",
            "recipe_action": str(request.recipe_action or "custom"),
            "label": name,
            "command": str(request.command or ""),
            "cwd": ".",
            "timeout_sec": 120,
        }
        content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        return [self._write_file(".embedagent/recipes/%s.json" % slug, content, "recipe", request.overwrite, diagnostics)]

    def _write_extension(self, slug: str, name: str, request: AuthoringRequest, diagnostics: List[Dict[str, Any]]) -> List[AuthoredFile]:
        extension_id = slug.replace("-", "_")
        manifest = {
            "id": extension_id,
            "enabled": False,
            "entrypoint": "extension.py",
            "description": request.summary or name,
            "permissions": list(request.permissions or ["read"]),
        }
        manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        extension_py = _extension_template(extension_id)
        readme = "# %s\n\nThis project-local extension is disabled by default. Review `extension.py`, then set `enabled` to `true` in `extension.json` only after you trust it.\n" % name
        validate_recipe = json.dumps(
            {
                "id": "local.%s.validate" % extension_id,
                "tool_name": "run_recipe",
                "recipe_action": "test",
                "label": "Validate %s" % name,
                "command": "python -m py_compile .embedagent/extensions/%s/extension.py" % slug,
                "cwd": ".",
                "timeout_sec": 120,
            },
            indent=2,
            sort_keys=True,
        ) + "\n"
        base = ".embedagent/extensions/%s" % slug
        return [
            self._write_file("%s/extension.json" % base, manifest_text, "extension_manifest", request.overwrite, diagnostics),
            self._write_file("%s/extension.py" % base, extension_py, "extension_code", request.overwrite, diagnostics),
            self._write_file("%s/README.md" % base, readme, "extension_doc", request.overwrite, diagnostics),
            self._write_file("%s/recipes/validate.json" % base, validate_recipe, "extension_recipe", request.overwrite, diagnostics),
        ]

    def _write_file(self, relative_path: str, content: str, kind: str, overwrite: bool, diagnostics: List[Dict[str, Any]]) -> AuthoredFile:
        path = _resolve_inside(self.workspace, relative_path)
        if os.path.exists(path) and not overwrite:
            diagnostics.append({"kind": kind, "path": _display_path(self.workspace, path), "error": "file already exists"})
            return AuthoredFile(_display_path(self.workspace, path), kind, "skipped")
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return AuthoredFile(_display_path(self.workspace, path), kind, "written")


def _failed(kind: str, name: str, slug: str, error: str) -> AuthoringResult:
    return AuthoringResult(
        success=False,
        kind=str(kind or ""),
        name=str(name or ""),
        slug=str(slug or ""),
        diagnostics=[{"kind": str(kind or "authoring"), "error": str(error or "")}],
    )


def _slugify(name: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", str(name or "").strip().lower())
    return text.strip("-")


def _resolve_inside(workspace: str, relative_path: str) -> str:
    base = os.path.realpath(workspace)
    path = os.path.realpath(os.path.join(base, str(relative_path or "")))
    base_norm = os.path.normcase(base)
    path_norm = os.path.normcase(path)
    if path_norm == base_norm or path_norm.startswith(base_norm + os.sep):
        return path
    raise ValueError("path is outside workspace: %s" % relative_path)


def _display_path(workspace: str, path: str) -> str:
    try:
        relative = os.path.relpath(path, workspace)
    except ValueError:
        return os.path.realpath(path)
    return "." if relative == "." else relative.replace(os.sep, "/")


def _next_actions(kind: str) -> List[str]:
    if kind in ("skill", "prompt", "recipe"):
        return ["Run /resources reload to refresh local file resources."]
    return [
        "Review generated extension files before enabling the manifest.",
        "Resource reload will not execute extension.py.",
        "Project extension loading is separate and requires enabled=true plus declared permissions.",
    ]


def _extension_template(extension_id: str) -> str:
    return '''from __future__ import annotations


def create_extension(api):
    class ProjectExtension(object):
        extension_id = api.extension_id
        builtin_extension = False

        # Example: expose extra resource paths without executing code during resource reload.
        # def resources_discover(self, event, context):
        #     return api.ResourcesDiscoverResult(skill_paths=[".embedagent/skills"])

        # Example: activate a read-only dynamic tool after adding register_tools().
        # def allowed_tool_names(self, mode_name, workflow_state="chat"):
        #     return set()

    return ProjectExtension()
'''
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_self_extension_authoring.py::test_authors_skill_prompt_recipe_and_disabled_extension -q
```

Expected: PASS.

- [ ] **Step 5: Add safety tests for invalid names, no overwrite, and invalid permissions**

Append to `tests/test_self_extension_authoring.py`:

```python
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
```

- [ ] **Step 6: Run safety tests**

Run:

```bash
uv run pytest tests/test_self_extension_authoring.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit E-A**

Run:

```bash
git add src/embedagent/self_extension_authoring.py tests/test_self_extension_authoring.py
git commit -m "feat: add self-extension authoring service"
```

---

## Task E-B: Runtime Tool Surface

**Files:**
- Create: `src/embedagent/tools/authoring_ops.py`
- Modify: `src/embedagent/tools/runtime.py`
- Modify: `src/embedagent/modes.py`
- Modify: `tests/test_tools_package.py`

- [ ] **Step 1: Write failing tests for tool schema and execution**

Add to `tests/test_tools_package.py`:

```python
    def test_author_local_capability_schema_is_build_debug_only(self):
        build_names = [
            item["function"]["name"] for item in self.rt.schemas_for("build", workflow_state="chat")
        ]
        debug_names = [
            item["function"]["name"] for item in self.rt.schemas_for("debug", workflow_state="chat")
        ]
        verify_names = [
            item["function"]["name"] for item in self.rt.schemas_for("verify", workflow_state="review")
        ]

        self.assertIn("author_local_capability", build_names)
        self.assertIn("author_local_capability", debug_names)
        self.assertNotIn("author_local_capability", verify_names)

    def test_author_local_capability_writes_skill_artifact(self):
        obs = self.rt.execute(
            "author_local_capability",
            {
                "kind": "skill",
                "name": "Review Helper",
                "summary": "Review local changes.",
            },
        )

        self.assertTrue(obs.success)
        self.assertEqual(obs.data["kind"], "skill")
        self.assertTrue(
            os.path.isfile(os.path.join(self.workspace, ".embedagent", "skills", "review-helper.md"))
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestToolRuntimeSchemas::test_author_local_capability_schema_is_build_debug_only tests/test_tools_package.py::TestToolRuntimeSchemas::test_author_local_capability_writes_skill_artifact -q
```

Expected: FAIL because the tool is not registered yet.

- [ ] **Step 3: Create `authoring_ops` tool**

Create `src/embedagent/tools/authoring_ops.py`:

```python
from __future__ import annotations

from typing import Any, Dict, List

from embedagent.self_extension_authoring import AuthoringRequest, SelfExtensionAuthoringService
from embedagent.session import Observation
from embedagent.tools._base import ToolContext, ToolDefinition


def build_tools(ctx: ToolContext) -> List[ToolDefinition]:
    def _author_local_capability(arguments: Dict[str, Any]) -> Observation:
        result = SelfExtensionAuthoringService(ctx.workspace).author(
            AuthoringRequest(
                kind=str(arguments.get("kind") or ""),
                name=str(arguments.get("name") or ""),
                summary=str(arguments.get("summary") or ""),
                body=str(arguments.get("body") or ""),
                command=str(arguments.get("command") or ""),
                recipe_action=str(arguments.get("recipe_action") or "custom"),
                permissions=list(arguments.get("permissions") or ["read"]),
                overwrite=bool(arguments.get("overwrite", False)),
            )
        )
        return Observation(
            tool_name="author_local_capability",
            success=result.success,
            error=None if result.success else "; ".join(item.get("error", "") for item in result.diagnostics),
            data=result.to_dict(),
        )

    return [
        ToolDefinition(
            name="author_local_capability",
            description=(
                "Create local self-extension artifacts under .embedagent. "
                "This writes skills, prompts, recipes, or disabled project extension skeletons; "
                "it does not reload resources or load Python extensions."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["skill", "prompt", "recipe", "extension"],
                    },
                    "name": {"type": "string"},
                    "summary": {"type": "string"},
                    "body": {"type": "string"},
                    "command": {"type": "string"},
                    "recipe_action": {"type": "string"},
                    "permissions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "overwrite": {"type": "boolean"},
                },
                "required": ["kind", "name"],
                "additionalProperties": False,
            },
            handler=_author_local_capability,
            read_only=False,
            concurrency_safe=False,
        )
    ]
```

- [ ] **Step 4: Register tool and metadata**

Modify `src/embedagent/tools/runtime.py`:

```python
from embedagent.tools import (
    authoring_ops,
    compile_ops,
    discovery_ops,
    file_ops,
    git_ops,
    session_ops,
    shell_ops,
)
```

Add `_DEFAULT_TOOL_METADATA["author_local_capability"]`:

```python
    "author_local_capability": {
        "permission_category": "workspace_write",
        "mode_visibility": ["build", "debug"],
        "workflow_visibility": ["chat", "plan", "command"],
        "user_label": "Author Local Capability",
        "progress_renderer_key": "file_write",
        "result_renderer_key": "file_write",
        "supports_diff_preview": True,
        "context_reducer_key": "author_local_capability",
        "read_only": False,
        "concurrency_safe": False,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "edit",
        "context_priority": 82,
    },
```

Add `authoring_ops.build_tools(self._ctx)` to `core_tools`.

Modify `src/embedagent/modes.py`:

```python
"author_local_capability",
```

Add the tool to `build.allowed_tools` and `debug.allowed_tools` only.

- [ ] **Step 5: Run tool tests**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestToolRuntimeSchemas::test_author_local_capability_schema_is_build_debug_only tests/test_tools_package.py::TestToolRuntimeSchemas::test_author_local_capability_writes_skill_artifact -q
```

Expected: PASS.

- [ ] **Step 6: Update total tool count test**

If `TestToolRuntimeSchemas.test_total_tool_count` fails, update expected count from `15` to `16`.

- [ ] **Step 7: Commit E-B**

Run:

```bash
uv run pytest tests/test_tools_package.py tests/test_tools_v2_runtime.py tests/test_permissions.py -q
git add src/embedagent/tools/authoring_ops.py src/embedagent/tools/runtime.py src/embedagent/modes.py tests/test_tools_package.py
git commit -m "feat: expose local capability authoring tool"
```

---

## Task E-C: Validation And Reload/Load Boundaries

**Files:**
- Modify: `tests/test_self_extension_authoring.py`
- Modify: `tests/test_local_resources.py`
- Modify: `tests/test_project_extensions.py`

- [ ] **Step 1: Add tests proving generated recipe is discovered only through reload**

Add to `tests/test_self_extension_authoring.py`:

```python
def test_generated_recipe_is_discovered_after_runtime_reload(tmp_path):
    from embedagent.self_extension_authoring import (
        AuthoringRequest,
        SelfExtensionAuthoringService,
    )
    from embedagent.tools import ToolRuntime

    runtime = ToolRuntime(str(tmp_path))
    before = runtime.workspace_recipes()
    result = SelfExtensionAuthoringService(str(tmp_path)).author(
        AuthoringRequest(
            kind="recipe",
            name="Author Verify",
            command="cmd /c echo author-verify",
            recipe_action="test",
        )
    )
    after_write = runtime.workspace_recipes()
    reloaded = runtime.reload_resources(reason="authoring-test")
    after_reload = runtime.workspace_recipes()

    assert result.success is True
    assert "local.author_verify" not in [item["id"] for item in before["items"]]
    assert "local.author_verify" not in [item["id"] for item in after_write["items"]]
    assert reloaded["counts"]["recipes"] == 1
    assert "local.author_verify" in [item["id"] for item in after_reload["items"]]
```

- [ ] **Step 2: Add test proving generated extension is disabled and not imported**

Add to `tests/test_self_extension_authoring.py`:

```python
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
    extension_py.write_text("raise RuntimeError('should not import while disabled')\n", encoding="utf-8")

    payload = load_project_extensions(str(tmp_path))

    assert result.success is True
    assert payload["counts"]["disabled"] == 1
    assert payload["counts"]["loaded"] == 0
    assert payload["diagnostics"] == []
```

- [ ] **Step 3: Run boundary tests**

Run:

```bash
uv run pytest tests/test_self_extension_authoring.py tests/test_local_resources.py tests/test_project_extensions.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit E-C**

Run:

```bash
git add tests/test_self_extension_authoring.py
git commit -m "test: guard self-extension reload and load boundaries"
```

---

## Task E-D: Focused Integration Verification

**Files:**
- Modify only if a regression is found.

- [ ] **Step 1: Run focused architecture suites**

Run:

```bash
uv run pytest tests/test_self_extension_authoring.py tests/test_local_resources.py tests/test_project_extensions.py tests/test_dynamic_tool_registration.py tests/test_workflow_extensions.py tests/test_query_engine_refactor.py tests/test_inprocess_adapter_frontend_api.py -q
```

Expected: PASS.

- [ ] **Step 2: Run lint/format**

Run:

```bash
uv run ruff check src/ tests/
uv run black --check src/ tests/
```

Expected: both pass.

- [ ] **Step 3: Commit only if fixes were required**

If Step 1 or Step 2 required changes:

```bash
git add src tests
git commit -m "test: verify self-extension authoring integration"
```

If no changes were required, do not create an empty commit.

---

## Task E-E: Documentation Closeout

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/permission-model.md`
- Move: `docs/superpowers/specs/2026-06-14-phase-e-self-extension-authoring-design.md`
- Move: `docs/superpowers/plans/2026-06-14-phase-e-self-extension-authoring.md`

- [ ] **Step 1: Update source-of-truth docs**

Document:

- Phase E complete.
- `SelfExtensionAuthoringService` owns local artifact authoring.
- `author_local_capability` is a workflow-neutral built-in write tool.
- Generated project extensions are disabled by default.
- Resource reload remains separate from project extension loading.
- No online registry, dependency installation, marketplace, built-in replacement, or remote code.

- [ ] **Step 2: Archive Phase E slice docs**

Run:

```powershell
New-Item -ItemType Directory -Force docs\archive\phase-e-self-extension-authoring
Move-Item docs\superpowers\specs\2026-06-14-phase-e-self-extension-authoring-design.md docs\archive\phase-e-self-extension-authoring\
Move-Item docs\superpowers\plans\2026-06-14-phase-e-self-extension-authoring.md docs\archive\phase-e-self-extension-authoring\
```

- [ ] **Step 3: Scan for stale Phase E status**

Run:

```bash
rg -n "Phase E.*(next|pending|准备)|下一步进入 Phase E|self-extension authoring loop.*pending|docs/superpowers/.+phase-e" README.md AGENTS.md docs --glob "!docs/archive/**"
```

Expected: no stale active-doc hits.

- [ ] **Step 4: Full verification**

Run:

```bash
uv run ruff check src/ tests/
uv run black --check src/ tests/
uv run pytest tests/ -m "not slow and not gui" -q
```

Expected: all pass.

- [ ] **Step 5: Commit closeout**

Run:

```bash
git add README.md AGENTS.md docs src tests
git commit -m "docs: close phase e self-extension authoring loop"
```

---

## Self-Review Checklist

- Spec coverage: Tasks E-A through E-E cover service, tool surface, reload/load boundary validation, integration verification, and docs closeout.
- Placeholder scan: no `TBD`, `TODO`, or open-ended implementation steps.
- Type consistency: `AuthoringRequest`, `AuthoredFile`, `AuthoringResult`, `SelfExtensionAuthoringService`, and `author_local_capability` names are consistent across tasks.
- Boundary check: no task loads generated extension code through resource reload.
- Scope check: frontend endpoint work is deferred; first slice is service/tool-first.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-14-phase-e-self-extension-authoring.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Recommended here: Inline execution, because the write set is small and the current tool policy only allows subagents when explicitly requested.
