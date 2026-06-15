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
            str(item or "").strip()
            for item in request.permissions
            if str(item or "").strip() not in _VALID_PERMISSION
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

    def _write_skill(
        self,
        slug: str,
        name: str,
        request: AuthoringRequest,
        diagnostics: List[Dict[str, Any]],
    ) -> List[AuthoredFile]:
        description = request.summary or "Describe the local skill purpose."
        content = (
            "---\n"
            "name: %s\n"
            "description: %s\n"
            "disable-model-invocation: false\n"
            "---\n\n"
            "# %s\n\n"
            "## Purpose\n\n%s\n\n"
            "## When To Use\n\nDescribe when this local skill should guide the agent.\n\n"
            "## Inputs\n\n- Workspace context\n- User request\n\n"
            "## Output Contract\n\nState the expected output clearly.\n\n"
            "## Validation\n\nReload local resources after editing this file.\n"
        ) % (slug, _frontmatter_value(description), name, description)
        return [
            self._write_file(
                ".embedagent/skills/%s.md" % slug,
                content,
                "skill",
                request.overwrite,
                diagnostics,
            )
        ]

    def _write_prompt(
        self,
        slug: str,
        name: str,
        request: AuthoringRequest,
        diagnostics: List[Dict[str, Any]],
    ) -> List[AuthoredFile]:
        content = (
            "# %s\n\n"
            "## Intended Use\n\n%s\n\n"
            "## Prompt\n\n%s\n\n"
            "## Safety Notes\n\nKeep this prompt local to the workspace and reload resources after editing.\n"
        ) % (
            name,
            request.summary or "Describe when this prompt should be used.",
            request.body or "Write the prompt body here.",
        )
        return [
            self._write_file(
                ".embedagent/prompts/%s.md" % slug,
                content,
                "prompt",
                request.overwrite,
                diagnostics,
            )
        ]

    def _write_recipe(
        self,
        slug: str,
        name: str,
        request: AuthoringRequest,
        diagnostics: List[Dict[str, Any]],
    ) -> List[AuthoredFile]:
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
        return [
            self._write_file(
                ".embedagent/recipes/%s.json" % slug,
                content,
                "recipe",
                request.overwrite,
                diagnostics,
            )
        ]

    def _write_extension(
        self,
        slug: str,
        name: str,
        request: AuthoringRequest,
        diagnostics: List[Dict[str, Any]],
    ) -> List[AuthoredFile]:
        extension_id = slug.replace("-", "_")
        manifest = {
            "id": extension_id,
            "enabled": False,
            "entrypoint": "extension.py",
            "description": request.summary or name,
            "permissions": list(request.permissions or ["read"]),
        }
        manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        extension_py = _extension_template()
        readme = (
            "# %s\n\n"
            "This project-local extension is disabled by default. Review `extension.py`, "
            "then set `enabled` to `true` in `extension.json` only after you trust it.\n"
        ) % name
        validate_recipe = (
            json.dumps(
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
            )
            + "\n"
        )
        base = ".embedagent/extensions/%s" % slug
        return [
            self._write_file(
                "%s/extension.json" % base,
                manifest_text,
                "extension_manifest",
                request.overwrite,
                diagnostics,
            ),
            self._write_file(
                "%s/extension.py" % base,
                extension_py,
                "extension_code",
                request.overwrite,
                diagnostics,
            ),
            self._write_file(
                "%s/README.md" % base,
                readme,
                "extension_doc",
                request.overwrite,
                diagnostics,
            ),
            self._write_file(
                "%s/recipes/validate.json" % base,
                validate_recipe,
                "extension_recipe",
                request.overwrite,
                diagnostics,
            ),
        ]

    def _write_file(
        self,
        relative_path: str,
        content: str,
        kind: str,
        overwrite: bool,
        diagnostics: List[Dict[str, Any]],
    ) -> AuthoredFile:
        path = _resolve_inside(self.workspace, relative_path)
        display_path = _display_path(self.workspace, path)
        if os.path.exists(path) and not overwrite:
            diagnostics.append({"kind": kind, "path": display_path, "error": "file already exists"})
            return AuthoredFile(display_path, kind, "skipped")
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return AuthoredFile(display_path, kind, "written")


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


def _frontmatter_value(value: str) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text or "Describe the local skill purpose."


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


def _extension_template() -> str:
    return """from __future__ import annotations


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
"""
