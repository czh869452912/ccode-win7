from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


_PROJECT_RECIPES_RELPATH = os.path.join(".embedagent", "workspace-recipes.json")
_HISTORY_RECIPES_RELPATH = os.path.join(".embedagent", "memory", "project", "command-recipes.json")


def list_workspace_recipes(workspace: str) -> Dict[str, Any]:
    workspace = os.path.realpath(workspace)
    items = []  # type: List[Dict[str, Any]]
    items.extend(_load_project_recipes(workspace))
    items.extend(_detect_builtin_recipes(workspace))
    items.extend(_load_history_recipes(workspace))
    return {
        "workspace": workspace,
        "items": items,
    }


def resolve_workspace_recipe(
    workspace: str,
    recipe_id: str,
    expected_tool_name: str = "",
    target: str = "",
    profile: str = "",
) -> Dict[str, Any]:
    payload = list_workspace_recipes(workspace)
    normalized_id = str(recipe_id or "").strip()
    normalized_expected = str(expected_tool_name or "").strip()
    for item in payload.get("items") or []:
        if str(item.get("id") or "") != normalized_id:
            continue
        tool_name = str(item.get("tool_name") or "")
        if normalized_expected and tool_name != normalized_expected:
            raise ValueError("recipe %s 不支持工具 %s。" % (normalized_id, normalized_expected))
        resolved = dict(item)
        resolved["cwd"] = str(item.get("cwd") or ".")
        if str(item.get("family") or "") == "cmake":
            build_dir = "build"
            normalized_profile = str(profile or "").strip()
            if normalized_profile and normalized_profile.lower() not in ("default", "build"):
                build_dir = "build/%s" % normalized_profile.replace("\\", "/")
            stage = str(item.get("stage") or "")
            if stage == "configure":
                resolved["command"] = "cmake -S . -B %s" % build_dir
            elif stage == "build":
                command = "cmake --build %s" % build_dir
                normalized_target = str(target or "").strip()
                if normalized_target:
                    command += " --target %s" % normalized_target
                resolved["command"] = command
            elif stage == "test":
                resolved["command"] = "ctest --test-dir %s --output-on-failure" % build_dir
        if not resolved.get("command"):
            raise ValueError("recipe %s 缺少 command。" % normalized_id)
        resolved["recipe_id"] = normalized_id
        resolved["profile"] = str(profile or "")
        resolved["target"] = str(target or "")
        return resolved
    raise ValueError("未找到 recipe：%s" % normalized_id)


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
        items.append(
            {
                "id": recipe_id,
                "tool_name": tool_name,
                "label": str(entry.get("label") or recipe_id),
                "command": command,
                "cwd": str(entry.get("cwd") or "."),
                "source": "project",
            }
        )
    return items


def _detect_builtin_recipes(workspace: str) -> List[Dict[str, Any]]:
    items = []
    if os.path.isfile(os.path.join(workspace, "CMakeLists.txt")):
        items.extend(
            [
                {
                    "id": "cmake.configure.default",
                    "tool_name": "compile_project",
                    "label": "CMake Configure",
                    "command": "cmake -S . -B build",
                    "cwd": ".",
                    "source": "detected",
                    "family": "cmake",
                    "stage": "configure",
                    "supports_target": False,
                    "supports_profile": True,
                },
                {
                    "id": "cmake.build.default",
                    "tool_name": "compile_project",
                    "label": "CMake Build",
                    "command": "cmake --build build",
                    "cwd": ".",
                    "source": "detected",
                    "family": "cmake",
                    "stage": "build",
                    "supports_target": True,
                    "supports_profile": True,
                },
                {
                    "id": "cmake.test.default",
                    "tool_name": "run_tests",
                    "label": "CTest",
                    "command": "ctest --test-dir build --output-on-failure",
                    "cwd": ".",
                    "source": "detected",
                    "family": "cmake",
                    "stage": "test",
                    "supports_target": False,
                    "supports_profile": True,
                },
            ]
        )
    makefile = ""
    for name in ("Makefile", "makefile"):
        candidate = os.path.join(workspace, name)
        if os.path.isfile(candidate):
            makefile = candidate
            break
    if makefile:
        items.extend(
            [
                {
                    "id": "make.build.default",
                    "tool_name": "compile_project",
                    "label": "Make Build",
                    "command": "make",
                    "cwd": ".",
                    "source": "detected",
                    "family": "make",
                    "stage": "build",
                    "supports_target": False,
                    "supports_profile": False,
                },
                {
                    "id": "make.test.default",
                    "tool_name": "run_tests",
                    "label": "Make Test",
                    "command": "make test",
                    "cwd": ".",
                    "source": "detected",
                    "family": "make",
                    "stage": "test",
                    "supports_target": False,
                    "supports_profile": False,
                },
            ]
        )
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
        if not tool_name or not command:
            continue
        counts[tool_name] = int(counts.get(tool_name) or 0) + 1
        items.append(
            {
                "id": "history.%s.%s" % (tool_name, counts[tool_name]),
                "tool_name": tool_name,
                "label": "History %s" % tool_name,
                "command": command,
                "cwd": str(entry.get("cwd") or "."),
                "source": "history",
            }
        )
    return items


def _load_json(path: str, default: Any) -> Any:
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default
