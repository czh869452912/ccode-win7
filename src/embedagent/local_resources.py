from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from embedagent.skills import discover_skill_resources

DEFAULT_SKILL_RELPATH = os.path.join(".embedagent", "skills")
DEFAULT_PROMPT_RELPATH = os.path.join(".embedagent", "prompts")
DEFAULT_RECIPE_RELPATH = os.path.join(".embedagent", "recipes")

PROMPT_EXTENSIONS = (".md", ".txt")
RECIPE_EXTENSIONS = (".json",)


def discover_local_resources(
    workspace: str,
    skill_paths: Optional[List[str]] = None,
    prompt_paths: Optional[List[str]] = None,
    recipe_paths: Optional[List[str]] = None,
    reason: str = "startup",
) -> Dict[str, Any]:
    workspace_root = os.path.realpath(workspace)
    diagnostics = []  # type: List[Dict[str, Any]]
    resolved_skill_paths = _resolve_resource_paths(
        workspace_root,
        [DEFAULT_SKILL_RELPATH] + list(skill_paths or []),
        diagnostics,
        "skill",
    )
    resolved_prompt_paths = _resolve_resource_paths(
        workspace_root,
        [DEFAULT_PROMPT_RELPATH] + list(prompt_paths or []),
        diagnostics,
        "prompt",
    )
    resolved_recipe_paths = _resolve_resource_paths(
        workspace_root,
        [DEFAULT_RECIPE_RELPATH] + list(recipe_paths or []),
        diagnostics,
        "recipe",
    )
    skills = discover_skill_resources(
        workspace_root,
        resolved_skill_paths,
        diagnostics,
    )
    prompts = _discover_text_resources(
        workspace_root,
        resolved_prompt_paths,
        PROMPT_EXTENSIONS,
        "prompt",
    )
    recipes = _discover_recipe_resources(workspace_root, resolved_recipe_paths, diagnostics)
    return {
        "workspace": workspace_root,
        "reason": str(reason or ""),
        "resource_paths": {
            "skill_paths": [_display_path(workspace_root, path) for path in resolved_skill_paths],
            "prompt_paths": [_display_path(workspace_root, path) for path in resolved_prompt_paths],
            "recipe_paths": [_display_path(workspace_root, path) for path in resolved_recipe_paths],
        },
        "counts": {
            "skills": len(skills),
            "prompts": len(prompts),
            "recipes": len(recipes),
            "diagnostics": len(diagnostics),
        },
        "skills": skills,
        "prompts": prompts,
        "recipes": recipes,
        "diagnostics": diagnostics,
    }


def _resolve_resource_paths(
    workspace: str,
    raw_paths: List[str],
    diagnostics: List[Dict[str, Any]],
    kind: str,
) -> List[str]:
    resolved = []  # type: List[str]
    seen = set()
    for raw_path in raw_paths:
        text = str(raw_path or "").strip()
        if not text:
            continue
        candidate = text if os.path.isabs(text) else os.path.join(workspace, text)
        path = os.path.realpath(candidate)
        if not _is_within_workspace(workspace, path):
            diagnostics.append(
                {
                    "kind": kind,
                    "path": text,
                    "error": "resource path is outside workspace",
                }
            )
            continue
        key = os.path.normcase(path)
        if key in seen:
            continue
        seen.add(key)
        resolved.append(path)
    return resolved


def _discover_text_resources(
    workspace: str,
    roots: List[str],
    extensions: tuple,
    kind: str,
) -> List[Dict[str, Any]]:
    items = []  # type: List[Dict[str, Any]]
    for path in _iter_resource_files(roots, extensions):
        items.append(
            {
                "kind": kind,
                "path": _display_path(workspace, path),
                "name": os.path.splitext(os.path.basename(path))[0],
                "source": "local_resource",
            }
        )
    return items


def _discover_recipe_resources(
    workspace: str,
    roots: List[str],
    diagnostics: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    recipes = []  # type: List[Dict[str, Any]]
    seen_ids = set()
    for path in _iter_resource_files(roots, RECIPE_EXTENSIONS):
        payload = _load_recipe_payload(path, workspace, diagnostics)
        if payload is None:
            continue
        entries = payload if isinstance(payload, list) else [payload]
        for entry in entries:
            if not isinstance(entry, dict):
                diagnostics.append(
                    {
                        "kind": "recipe",
                        "path": _display_path(workspace, path),
                        "error": "recipe entry must be an object",
                    }
                )
                continue
            recipe = _normalize_recipe(entry, workspace, path, diagnostics)
            if not recipe:
                continue
            recipe_id = str(recipe.get("id") or "")
            if recipe_id in seen_ids:
                diagnostics.append(
                    {
                        "kind": "recipe",
                        "path": _display_path(workspace, path),
                        "error": "duplicate recipe id: %s" % recipe_id,
                    }
                )
                continue
            seen_ids.add(recipe_id)
            recipes.append(recipe)
    return recipes


def _load_recipe_payload(
    path: str,
    workspace: str,
    diagnostics: List[Dict[str, Any]],
) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        diagnostics.append(
            {
                "kind": "recipe",
                "path": _display_path(workspace, path),
                "error": str(exc),
            }
        )
        return None


def _normalize_recipe(
    entry: Dict[str, Any],
    workspace: str,
    path: str,
    diagnostics: List[Dict[str, Any]],
) -> Dict[str, Any]:
    recipe_id = str(entry.get("id") or "").strip()
    command = str(entry.get("command") or "").strip()
    if not recipe_id or not command:
        diagnostics.append(
            {
                "kind": "recipe",
                "path": _display_path(workspace, path),
                "error": "recipe requires id and command",
            }
        )
        return {}
    recipe_action = str(entry.get("recipe_action") or entry.get("stage") or "custom").strip()
    return {
        "id": recipe_id,
        "tool_name": str(entry.get("tool_name") or ""),
        "recipe_action": recipe_action,
        "label": str(entry.get("label") or recipe_id),
        "command": command,
        "cwd": str(entry.get("cwd") or "."),
        "source": "local_resource",
        "resource_path": _display_path(workspace, path),
        "family": str(entry.get("family") or ""),
        "stage": str(entry.get("stage") or ""),
        "supports_target": bool(entry.get("supports_target", False)),
        "supports_profile": bool(entry.get("supports_profile", False)),
        "timeout_sec": int(entry.get("timeout_sec") or 120),
    }


def _iter_resource_files(roots: List[str], extensions: tuple) -> List[str]:
    files = []  # type: List[str]
    for root in roots:
        if os.path.isfile(root):
            if root.lower().endswith(extensions):
                files.append(root)
            continue
        if not os.path.isdir(root):
            continue
        for current_root, dir_names, file_names in os.walk(root):
            dir_names[:] = sorted(name for name in dir_names if name not in (".git", "__pycache__"))
            for file_name in sorted(file_names):
                absolute_path = os.path.join(current_root, file_name)
                if absolute_path.lower().endswith(extensions):
                    files.append(os.path.realpath(absolute_path))
    files.sort()
    return files


def _is_within_workspace(workspace: str, path: str) -> bool:
    workspace_norm = os.path.normcase(os.path.realpath(workspace))
    path_norm = os.path.normcase(os.path.realpath(path))
    return path_norm == workspace_norm or path_norm.startswith(workspace_norm + os.sep)


def _display_path(workspace: str, path: str) -> str:
    try:
        relative = os.path.relpath(path, workspace)
    except ValueError:
        return os.path.realpath(path)
    return "." if relative == "." else relative.replace(os.sep, "/")
