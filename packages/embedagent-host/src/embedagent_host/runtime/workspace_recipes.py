from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from embedagent_host.runtime.local_resources import discover_local_resources

_PROJECT_RECIPES_RELPATH = os.path.join(".embedagent", "workspace-recipes.json")
_HISTORY_RECIPES_RELPATH = os.path.join(".embedagent", "memory", "project", "command-recipes.json")


class RecipeResolutionError(ValueError):
    def __init__(self, message: str, payload: Dict[str, Any]) -> None:
        super(RecipeResolutionError, self).__init__(message)
        self.payload = payload


def list_workspace_recipes(
    workspace: str,
    resource_paths: Dict[str, List[str]] = None,
) -> Dict[str, Any]:
    workspace = os.path.realpath(workspace)
    source_payload = workspace_recipe_sources(workspace, resource_paths=resource_paths)
    items = [
        _normalize_recipe_item(item)
        for item in list(source_payload.get("items") or [])
        if isinstance(item, dict)
    ]
    return {
        "workspace": workspace,
        "items": items,
        "resources": dict(source_payload.get("resources") or {}),
    }


def workspace_recipe_sources(
    workspace: str,
    resource_paths: Dict[str, List[str]] = None,
) -> Dict[str, Any]:
    workspace = os.path.realpath(workspace)
    resource_payload = discover_local_resources(
        workspace,
        recipe_paths=list((resource_paths or {}).get("recipe_paths") or []),
        reason="recipes",
    )
    items = []  # type: List[Dict[str, Any]]
    items.extend(_load_project_recipes(workspace))
    items.extend(list(resource_payload.get("recipes") or []))
    items.extend(_load_history_recipes(workspace))
    return {
        "workspace": workspace,
        "items": items,
        "resources": {
            "counts": dict(resource_payload.get("counts") or {}),
            "diagnostics": list(resource_payload.get("diagnostics") or []),
            "resource_paths": dict(resource_payload.get("resource_paths") or {}),
        },
    }


def resolve_workspace_recipe(
    workspace: str,
    recipe_id: str,
    expected_tool_name: str = "",
    target: str = "",
    profile: str = "",
    resource_paths: Dict[str, List[str]] = None,
) -> Dict[str, Any]:
    del target, profile
    workspace = os.path.realpath(workspace)
    payload = list_workspace_recipes(workspace, resource_paths=resource_paths)
    items = list(payload.get("items") or [])
    normalized_id = str(recipe_id or "").strip()
    normalized_expected = str(expected_tool_name or "").strip()
    available = [str(item.get("id") or "") for item in items if item.get("id")]

    for item in items:
        if str(item.get("id") or "") != normalized_id:
            continue
        tool_name = str(item.get("tool_name") or "")
        if normalized_expected and normalized_expected != tool_name:
            raise RecipeResolutionError(
                "recipe %s does not support tool %s" % (normalized_id, normalized_expected),
                {
                    "error_kind": "recipe_tool_mismatch",
                    "retryable": False,
                    "recipe_id": normalized_id,
                    "expected_tool_name": normalized_expected,
                    "actual_tool_name": tool_name,
                    "available_recipes": available,
                    "suggested_next_step": "Choose an available recipe for this workflow.",
                },
            )

        resolved = dict(item)
        resolved["cwd"] = str(item.get("cwd") or ".")

        if not bool(resolved.get("ready", True)):
            raise RecipeResolutionError(
                str(resolved.get("reason") or "recipe prerequisites are missing"),
                {
                    "error_kind": "recipe_prerequisite_missing",
                    "retryable": False,
                    "recipe_id": normalized_id,
                    "recipe_label": str(resolved.get("label") or normalized_id),
                    "recipe_source": str(resolved.get("source") or ""),
                    "requires": list(resolved.get("requires") or []),
                    "reason": str(resolved.get("reason") or ""),
                    "suggested_next_step": str(
                        resolved.get("suggested_next_step")
                        or "Satisfy recipe prerequisites before running it."
                    ),
                    "available_recipes": available,
                },
            )

        if not resolved.get("command"):
            raise RecipeResolutionError(
                "recipe %s is missing command" % normalized_id,
                {
                    "error_kind": "recipe_missing_command",
                    "retryable": False,
                    "recipe_id": normalized_id,
                    "available_recipes": available,
                    "suggested_next_step": "Inspect or edit the recipe definition.",
                },
            )
        resolved["recipe_id"] = normalized_id
        return resolved

    raise RecipeResolutionError(
        "recipe not found: %s" % normalized_id,
        {
            "error_kind": "recipe_not_found",
            "retryable": False,
            "recipe_id": normalized_id,
            "available_recipes": available,
            "suggested_next_step": "Choose an available workspace recipe.",
        },
    )


def _normalize_recipe_item(item: Dict[str, Any]) -> Dict[str, Any]:
    original_tool_name = str(item.get("tool_name") or "").strip()
    stage = str(item.get("stage") or "").strip()
    normalized = dict(item)
    if original_tool_name:
        normalized["tool_name"] = original_tool_name
    else:
        normalized.pop("tool_name", None)
    normalized["recipe_action"] = str(
        item.get("recipe_action") or _recipe_action_from(original_tool_name, stage)
    )
    normalized["ready"] = bool(item.get("ready", True))
    normalized["confidence"] = str(item.get("confidence") or "high")
    normalized["requires"] = list(item.get("requires") or [])
    normalized["reason"] = str(item.get("reason") or "")
    normalized["suggested_next_step"] = str(item.get("suggested_next_step") or "")
    normalized["last_success"] = str(item.get("last_success") or item.get("last_success_at") or "")
    normalized["failure_count"] = int(item.get("failure_count") or 0)
    normalized["last_failure_summary"] = str(item.get("last_failure_summary") or "")
    return normalized


def _recipe_action_from(tool_name: str, stage: str) -> str:
    del tool_name
    normalized_stage = str(stage or "").strip()
    if normalized_stage:
        return normalized_stage
    return "custom"


def _load_project_recipes(workspace: str) -> List[Dict[str, Any]]:
    path = os.path.join(workspace, _PROJECT_RECIPES_RELPATH)
    payload = _load_json(path, [])
    if not isinstance(payload, list):
        return []
    items = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        recipe_id = str(entry.get("id") or "").strip()
        tool_name = str(entry.get("tool_name") or "").strip()
        command = str(entry.get("command") or "").strip()
        if not recipe_id or not command:
            continue
        item = {
            "id": recipe_id,
            "recipe_action": str(entry.get("recipe_action") or "").strip()
            or _recipe_action_from(tool_name, ""),
            "label": str(entry.get("label") or recipe_id),
            "command": command,
            "cwd": str(entry.get("cwd") or "."),
            "source": "project",
            "ready": bool(entry.get("ready", True)),
            "confidence": str(entry.get("confidence") or "high"),
            "requires": list(entry.get("requires") or []),
            "reason": str(entry.get("reason") or ""),
            "suggested_next_step": str(entry.get("suggested_next_step") or ""),
        }
        if tool_name:
            item["tool_name"] = tool_name
        items.append(item)
    return items


def _load_history_recipes(workspace: str) -> List[Dict[str, Any]]:
    path = os.path.join(workspace, _HISTORY_RECIPES_RELPATH)
    payload = _load_json(path, [])
    if not isinstance(payload, list):
        return []
    items = []
    counts = {}  # type: Dict[str, int]
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        tool_name = str(entry.get("tool_name") or "").strip()
        command = str(entry.get("command") or "").strip()
        if not command:
            continue
        recipe_action = _recipe_action_from(tool_name, str(entry.get("recipe_action") or ""))
        counts[recipe_action] = int(counts.get(recipe_action) or 0) + 1
        item = {
            "id": "history.%s.%s" % (recipe_action, counts[recipe_action]),
            "label": "History %s" % (tool_name or recipe_action),
            "command": command,
            "cwd": str(entry.get("cwd") or "."),
            "source": "history",
            "recipe_action": recipe_action,
            "ready": True,
            "confidence": "medium",
            "last_success": str(entry.get("last_success_at") or ""),
        }
        if tool_name:
            item["tool_name"] = tool_name
        items.append(item)
    return items


def _load_json(path: str, default: Any) -> Any:
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError, ValueError):
        return default
