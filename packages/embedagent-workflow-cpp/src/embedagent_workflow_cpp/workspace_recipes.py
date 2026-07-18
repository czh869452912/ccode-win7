from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional

from embedagent_workflow_cpp.tool_names import (
    C_WORKFLOW_TOOL_LIST_RECIPES,
    C_WORKFLOW_TOOL_RUN_RECIPE,
)

_PROJECT_RECIPES_RELPATH = os.path.join(".embedagent", "workspace-recipes.json")
_HISTORY_RECIPES_RELPATH = os.path.join(".embedagent", "memory", "project", "command-recipes.json")


class RecipeResolutionError(ValueError):
    def __init__(self, message: str, payload: Dict[str, Any]) -> None:
        super(RecipeResolutionError, self).__init__(message)
        self.payload = payload


def list_workspace_recipes(
    workspace: str,
    local_recipe_records: Optional[Iterable[Dict[str, Any]]] = None,
    resource_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    workspace = os.path.realpath(workspace)
    items = []  # type: List[Dict[str, Any]]
    resource_records = workspace_recipe_records(workspace, local_recipe_records)
    resource_payload = dict(resource_metadata or {})
    items.extend(_load_project_recipes(workspace))
    items.extend(resource_records)
    items.extend(_detect_builtin_recipes(workspace))
    items.extend(_load_history_recipes(workspace))
    items = [_normalize_recipe_item(item) for item in items if isinstance(item, dict)]
    counts = dict(resource_payload.get("counts") or {})
    counts["recipes"] = len(resource_records)
    return {
        "workspace": workspace,
        "items": items,
        "resources": {
            "counts": counts,
            "diagnostics": list(resource_payload.get("diagnostics") or []),
            "resource_paths": dict(resource_payload.get("resource_paths") or {}),
        },
    }


def workspace_recipe_records(
    workspace: str,
    local_recipe_records: Optional[Iterable[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Normalize Host-discovered recipe records at the workflow boundary."""
    del workspace
    records = []  # type: List[Dict[str, Any]]
    for record in local_recipe_records or ():
        if not isinstance(record, dict):
            continue
        normalized = dict(record)
        recipe_id = str(normalized.get("id") or normalized.get("name") or "").strip()
        if not recipe_id:
            continue
        normalized["id"] = recipe_id
        normalized.setdefault("name", recipe_id)
        records.append(normalized)
    return records


def resolve_workspace_recipe(
    workspace: str,
    recipe_id: str,
    expected_tool_name: str = "",
    target: str = "",
    profile: str = "",
    local_recipe_records: Optional[Iterable[Dict[str, Any]]] = None,
    resource_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    workspace = os.path.realpath(workspace)
    payload = list_workspace_recipes(
        workspace,
        local_recipe_records=local_recipe_records,
        resource_metadata=resource_metadata,
    )
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
                    "suggested_next_step": "Pick a recipe returned by %s."
                    % C_WORKFLOW_TOOL_LIST_RECIPES,
                },
            )

        resolved = dict(item)
        resolved["cwd"] = str(item.get("cwd") or ".")
        _apply_dynamic_recipe_command(workspace, resolved, target=target, profile=profile)

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
        resolved["profile"] = str(profile or "")
        resolved["target"] = str(target or "")
        return resolved

    raise RecipeResolutionError(
        "recipe not found: %s" % normalized_id,
        {
            "error_kind": "recipe_not_found",
            "retryable": False,
            "recipe_id": normalized_id,
            "available_recipes": available,
            "suggested_next_step": (
                "Call %s and choose an available ready recipe." % C_WORKFLOW_TOOL_LIST_RECIPES
            ),
        },
    )


def _apply_dynamic_recipe_command(
    workspace: str,
    resolved: Dict[str, Any],
    target: str = "",
    profile: str = "",
) -> None:
    if str(resolved.get("family") or "") != "cmake":
        return
    build_dir = _cmake_build_dir(profile)
    stage = str(resolved.get("stage") or "")
    if stage == "configure":
        resolved["command"] = "cmake -S . -B %s" % build_dir
        resolved["ready"] = True
        return
    if stage in ("build", "test") and profile:
        _mark_cmake_stage_readiness(workspace, resolved, build_dir=build_dir)
    if stage == "build":
        command = "cmake --build %s" % build_dir
        normalized_target = str(target or "").strip()
        if normalized_target:
            command += " --target %s" % normalized_target
        resolved["command"] = command
    elif stage == "test":
        resolved["command"] = "ctest --test-dir %s --output-on-failure" % build_dir


def _normalize_recipe_item(item: Dict[str, Any]) -> Dict[str, Any]:
    original_tool_name = str(item.get("tool_name") or "").strip()
    stage = str(item.get("stage") or "").strip()
    normalized = dict(item)
    normalized["tool_name"] = C_WORKFLOW_TOOL_RUN_RECIPE
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
    normalized_stage = str(stage or "").strip()
    if normalized_stage:
        return normalized_stage
    if str(tool_name or "").strip() == C_WORKFLOW_TOOL_RUN_RECIPE:
        return "custom"
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
        if not recipe_id or not tool_name or not command:
            continue
        recipe_action = str(entry.get("recipe_action") or "").strip() or _recipe_action_from(
            tool_name, ""
        )
        items.append(
            {
                "id": recipe_id,
                "tool_name": tool_name,
                "recipe_action": recipe_action,
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
        )
    return items


def _detect_builtin_recipes(workspace: str) -> List[Dict[str, Any]]:
    items = []
    if os.path.isfile(os.path.join(workspace, "CMakeLists.txt")):
        build_dir = _cmake_build_dir("")
        configure = {
            "id": "cmake.configure.default",
            "tool_name": C_WORKFLOW_TOOL_RUN_RECIPE,
            "recipe_action": "configure",
            "label": "CMake Configure",
            "command": "cmake -S . -B build",
            "cwd": ".",
            "source": "detected",
            "family": "cmake",
            "stage": "configure",
            "supports_target": False,
            "supports_profile": True,
            "ready": True,
            "confidence": "medium",
            "suggested_next_step": "Run this configure recipe before build or test.",
        }
        build = {
            "id": "cmake.build.default",
            "tool_name": C_WORKFLOW_TOOL_RUN_RECIPE,
            "recipe_action": "build",
            "label": "CMake Build",
            "command": "cmake --build build",
            "cwd": ".",
            "source": "detected",
            "family": "cmake",
            "stage": "build",
            "supports_target": True,
            "supports_profile": True,
            "confidence": "medium",
        }
        test = {
            "id": "cmake.test.default",
            "tool_name": C_WORKFLOW_TOOL_RUN_RECIPE,
            "recipe_action": "test",
            "label": "CTest",
            "command": "ctest --test-dir build --output-on-failure",
            "cwd": ".",
            "source": "detected",
            "family": "cmake",
            "stage": "test",
            "supports_target": False,
            "supports_profile": True,
            "confidence": "medium",
        }
        _mark_cmake_stage_readiness(workspace, build, build_dir=build_dir)
        _mark_cmake_stage_readiness(workspace, test, build_dir=build_dir)
        items.extend([configure, build, test])

    makefile = _find_makefile(workspace)
    if makefile:
        has_test_target = _makefile_has_target(makefile, "test")
        items.extend(
            [
                {
                    "id": "make.build.default",
                    "tool_name": C_WORKFLOW_TOOL_RUN_RECIPE,
                    "recipe_action": "build",
                    "label": "Make Build",
                    "command": "make",
                    "cwd": ".",
                    "source": "detected",
                    "family": "make",
                    "stage": "build",
                    "supports_target": True,
                    "supports_profile": False,
                    "ready": True,
                    "confidence": "medium",
                    "suggested_next_step": "Run this recipe or use bash for a specific make target.",
                },
                {
                    "id": "make.test.default",
                    "tool_name": C_WORKFLOW_TOOL_RUN_RECIPE,
                    "recipe_action": "test",
                    "label": "Make Test",
                    "command": "make test",
                    "cwd": ".",
                    "source": "detected",
                    "family": "make",
                    "stage": "test",
                    "supports_target": False,
                    "supports_profile": False,
                    "ready": has_test_target,
                    "confidence": "medium" if has_test_target else "low",
                    "requires": [] if has_test_target else ["make.test.target"],
                    "reason": "" if has_test_target else "Makefile does not declare a test target.",
                    "suggested_next_step": (
                        "Use bash to inspect make targets before running tests."
                        if not has_test_target
                        else "Run this recipe to execute make test."
                    ),
                },
            ]
        )

    ninja_path = os.path.join(workspace, "build.ninja")
    if os.path.isfile(ninja_path):
        has_test_target = _text_file_contains(ninja_path, r"(?m)^(?:build\s+)?test\b")
        items.extend(
            [
                {
                    "id": "ninja.build.default",
                    "tool_name": C_WORKFLOW_TOOL_RUN_RECIPE,
                    "recipe_action": "build",
                    "label": "Ninja Build",
                    "command": "ninja",
                    "cwd": ".",
                    "source": "detected",
                    "family": "ninja",
                    "stage": "build",
                    "supports_target": True,
                    "supports_profile": False,
                    "ready": True,
                    "confidence": "medium",
                },
                {
                    "id": "ninja.test.default",
                    "tool_name": C_WORKFLOW_TOOL_RUN_RECIPE,
                    "recipe_action": "test",
                    "label": "Ninja Test",
                    "command": "ninja test",
                    "cwd": ".",
                    "source": "detected",
                    "family": "ninja",
                    "stage": "test",
                    "supports_target": False,
                    "supports_profile": False,
                    "ready": has_test_target,
                    "confidence": "medium" if has_test_target else "low",
                    "requires": [] if has_test_target else ["ninja.test.target"],
                    "reason": (
                        "" if has_test_target else "build.ninja does not declare a test target."
                    ),
                    "suggested_next_step": (
                        "Use bash to inspect ninja targets before running tests."
                        if not has_test_target
                        else "Run this recipe to execute ninja test."
                    ),
                },
            ]
        )
    return items


def _cmake_build_dir(profile: str) -> str:
    normalized_profile = str(profile or "").strip()
    if normalized_profile and normalized_profile.lower() not in ("default", "build"):
        return "build/%s" % normalized_profile.replace("\\", "/")
    return "build"


def _mark_cmake_stage_readiness(
    workspace: str,
    item: Dict[str, Any],
    build_dir: str,
) -> None:
    abs_build_dir = os.path.join(workspace, *build_dir.split("/"))
    ready = os.path.isdir(abs_build_dir)
    item["ready"] = ready
    item["requires"] = [] if ready else ["cmake.configure.default"]
    item["reason"] = "" if ready else "CMake build directory does not exist: %s" % build_dir
    item["suggested_next_step"] = (
        "Run cmake.configure.default before this recipe."
        if not ready
        else "Run this recipe or use bash for a more specific CMake command."
    )


def _find_makefile(workspace: str) -> str:
    for name in ("Makefile", "makefile"):
        candidate = os.path.join(workspace, name)
        if os.path.isfile(candidate):
            return candidate
    return ""


def _makefile_has_target(path: str, target: str) -> bool:
    escaped = re.escape(target)
    return _text_file_contains(path, r"(?m)^%s\s*:" % escaped)


def _text_file_contains(path: str, pattern: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            text = handle.read()
    except (OSError, ValueError):
        return False
    return re.search(pattern, text) is not None


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
        if not tool_name or not command:
            continue
        recipe_action = _recipe_action_from(tool_name, str(entry.get("recipe_action") or ""))
        counts[recipe_action] = int(counts.get(recipe_action) or 0) + 1
        items.append(
            {
                "id": "history.%s.%s" % (recipe_action, counts[recipe_action]),
                "tool_name": tool_name,
                "label": "History %s" % tool_name,
                "command": command,
                "cwd": str(entry.get("cwd") or "."),
                "source": "history",
                "recipe_action": recipe_action,
                "ready": True,
                "confidence": "medium",
                "last_success": str(entry.get("last_success_at") or ""),
            }
        )
    return items


def _load_json(path: str, default: Any) -> Any:
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError, ValueError):
        return default
