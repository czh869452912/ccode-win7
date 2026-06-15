from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


def _utc_now_string() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_app_home() -> str:
    override = os.environ.get("EMBEDAGENT_GUI_APP_HOME", "").strip()
    if override:
        return os.path.realpath(override)
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        return os.path.realpath(os.path.join(appdata, "EmbedAgent", "gui"))
    return os.path.realpath(os.path.join(os.path.expanduser("~"), ".embedagent", "gui"))


def canonical_workspace_path(path: str) -> str:
    raw = str(path or "").strip()
    if not raw:
        raise ValueError("workspace_path_required")
    return os.path.realpath(os.path.abspath(raw))


def workspace_id_for_path(path: str) -> str:
    canonical = os.path.normcase(canonical_workspace_path(path))
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()
    return "ws-" + digest[:16]


class WorkspaceRegistry(object):
    def __init__(
        self,
        storage_path: Optional[str] = None,
        clock: Optional[Callable[[], str]] = None,
    ) -> None:
        self.storage_path = os.path.realpath(
            storage_path or os.path.join(default_app_home(), "workspaces.json")
        )
        self._clock = clock or _utc_now_string

    def _read_payload(self) -> Dict[str, Any]:
        if not os.path.isfile(self.storage_path):
            return {"version": 1, "workspaces": []}
        try:
            with open(self.storage_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError, TypeError):
            return {"version": 1, "workspaces": []}
        if not isinstance(payload, dict):
            return {"version": 1, "workspaces": []}
        workspaces = payload.get("workspaces")
        if not isinstance(workspaces, list):
            workspaces = []
        return {"version": 1, "workspaces": workspaces}

    def _write_payload(self, payload: Dict[str, Any]) -> None:
        parent = os.path.dirname(self.storage_path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with open(self.storage_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)

    def _with_exists(self, record: Dict[str, Any]) -> Dict[str, Any]:
        item = dict(record)
        item["exists"] = os.path.isdir(str(item.get("path") or ""))
        return item

    def list_workspaces(self) -> List[Dict[str, Any]]:
        payload = self._read_payload()
        records = []
        for item in payload.get("workspaces", []):
            if not isinstance(item, dict):
                continue
            workspace_id = str(item.get("id") or "").strip()
            path = str(item.get("path") or "").strip()
            if not workspace_id or not path:
                continue
            records.append(self._with_exists(item))
        records.sort(key=lambda item: str(item.get("last_opened_at") or ""), reverse=True)
        return records

    def get(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        wanted = str(workspace_id or "").strip()
        for record in self.list_workspaces():
            if record.get("id") == wanted:
                return record
        return None

    def upsert_path(self, path: str, label: str = "") -> Dict[str, Any]:
        canonical = canonical_workspace_path(path)
        if not os.path.isdir(canonical):
            raise ValueError("workspace_not_found")
        workspace_id = workspace_id_for_path(canonical)
        now = self._clock()
        payload = self._read_payload()
        workspaces = []
        existing = None
        for item in payload.get("workspaces", []):
            if isinstance(item, dict) and item.get("id") == workspace_id:
                existing = item
            elif isinstance(item, dict):
                workspaces.append(item)
        next_record = {
            "id": workspace_id,
            "path": canonical,
            "label": str(label or "").strip() or os.path.basename(canonical) or canonical,
            "created_at": str((existing or {}).get("created_at") or now),
            "last_opened_at": now,
        }
        workspaces.append(next_record)
        self._write_payload({"version": 1, "workspaces": workspaces})
        return self._with_exists(next_record)

    def mark_opened(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        payload = self._read_payload()
        now = self._clock()
        found = None
        workspaces = []
        for item in payload.get("workspaces", []):
            if not isinstance(item, dict):
                continue
            if item.get("id") == workspace_id:
                updated = dict(item)
                updated["last_opened_at"] = now
                found = updated
                workspaces.append(updated)
            else:
                workspaces.append(item)
        if found is None:
            return None
        self._write_payload({"version": 1, "workspaces": workspaces})
        return self._with_exists(found)

    def remove(self, workspace_id: str) -> bool:
        wanted = str(workspace_id or "").strip()
        payload = self._read_payload()
        kept = []
        removed = False
        for item in payload.get("workspaces", []):
            if isinstance(item, dict) and item.get("id") == wanted:
                removed = True
                continue
            if isinstance(item, dict):
                kept.append(item)
        self._write_payload({"version": 1, "workspaces": kept})
        return removed
