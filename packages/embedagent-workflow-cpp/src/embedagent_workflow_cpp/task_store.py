from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List


def task_snapshot_path(workspace: str, session_id: str) -> str:
    return os.path.join(
        os.path.realpath(workspace),
        ".embedagent",
        "memory",
        "sessions",
        str(session_id or ""),
        "task-graph.json",
    )


def relative_task_snapshot_path(session_id: str) -> str:
    return os.path.join(
        ".embedagent", "memory", "sessions", str(session_id or ""), "task-graph.json"
    ).replace(os.sep, "/")


def save_task_snapshot(
    workspace: str,
    session_id: str,
    mode_name: str,
    workflow_state: str,
    discipline_profile: str,
    current_phase: str,
    task_summary: str,
    task_items: List[Dict[str, Any]],
    snapshot_schema_version: int = 2,
    source_event_count: int = 0,
    workflow_fingerprint: str = "",
) -> str:
    path = task_snapshot_path(workspace, session_id)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    payload = {
        "snapshot_schema_version": int(snapshot_schema_version or 2),
        "session_id": str(session_id or ""),
        "mode_name": str(mode_name or ""),
        "workflow_state": str(workflow_state or ""),
        "discipline_profile": str(discipline_profile or ""),
        "current_phase": str(current_phase or ""),
        "task_summary": str(task_summary or ""),
        "tasks": _normalize_items(task_items),
        "source_transcript_event_count": max(0, int(source_event_count or 0)),
        "source_workflow_fingerprint": str(workflow_fingerprint or ""),
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path


def load_task_snapshot(workspace: str, session_id: str) -> Dict[str, Any]:
    path = task_snapshot_path(workspace, session_id)
    if not session_id or not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    result = dict(payload)
    result["snapshot_schema_version"] = _safe_nonnegative_int(
        payload.get("snapshot_schema_version"), 1
    )
    result["source_transcript_event_count"] = _safe_nonnegative_int(
        payload.get("source_transcript_event_count"), 0
    )
    result["source_workflow_fingerprint"] = str(payload.get("source_workflow_fingerprint") or "")
    result["tasks"] = _normalize_items(payload.get("tasks"))
    return result


def load_task_items(workspace: str, session_id: str) -> List[Dict[str, Any]]:
    payload = load_task_snapshot(workspace, session_id)
    return list(payload.get("tasks") or [])


def pending_task_count(workspace: str, session_id: str) -> int:
    count = 0
    for item in load_task_items(workspace, session_id):
        if not bool(item.get("done")):
            count += 1
    return count


def _normalize_items(items: Any) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    result = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or item.get("title") or "").strip()
        status = str(item.get("status") or "").strip() or "pending"
        result.append(
            {
                "id": int(item.get("id") or index),
                "content": content,
                "status": status,
                "done": bool(item.get("done", status == "completed")),
                "note": str(item.get("note") or ""),
            }
        )
    return result


def workflow_fingerprint(workflow: Dict[str, Any]) -> str:
    canonical = json.dumps(
        workflow or {},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _safe_nonnegative_int(value: Any, default: int) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return max(0, int(default or 0))
