from __future__ import annotations

import json
import os
from typing import Any, Dict, List


_LEGACY_TODOS_RELPATH = os.path.join(".embedagent", "todos.json")
_SESSION_MEMORY_RELPATH = os.path.join(".embedagent", "memory", "sessions")


def legacy_todos_path(workspace: str) -> str:
    return os.path.join(os.path.realpath(workspace), _LEGACY_TODOS_RELPATH)


def session_todos_dir(workspace: str, session_id: str) -> str:
    return os.path.join(os.path.realpath(workspace), _SESSION_MEMORY_RELPATH, session_id)


def session_todos_path(workspace: str, session_id: str) -> str:
    if not session_id:
        raise ValueError("session_id 不能为空。")
    return os.path.join(session_todos_dir(workspace, session_id), "todos.json")


def relative_todos_path(session_id: str) -> str:
    if not session_id:
        return _LEGACY_TODOS_RELPATH.replace(os.sep, "/")
    return os.path.join(_SESSION_MEMORY_RELPATH, session_id, "todos.json").replace(os.sep, "/")


def load_todos(workspace: str, session_id: str = "") -> List[Dict[str, Any]]:
    path = legacy_todos_path(workspace) if not session_id else session_todos_path(workspace, session_id)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def save_todos(workspace: str, todos: List[Dict[str, Any]], session_id: str = "") -> str:
    if session_id:
        path = session_todos_path(workspace, session_id)
    else:
        path = legacy_todos_path(workspace)
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(todos, handle, ensure_ascii=False, indent=2)
    return path


def ensure_session_todos(workspace: str, session_id: str, seed_from_legacy: bool = False) -> str:
    path = session_todos_path(workspace, session_id)
    if os.path.isfile(path):
        return path
    todos = []
    if seed_from_legacy:
        todos = load_todos(workspace, session_id="")
    save_todos(workspace, todos, session_id=session_id)
    return path
