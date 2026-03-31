from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, Optional

from embedagent.protocol import PlanSnapshot


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class PlanStore(object):
    """Persist per-session plan snapshots under session memory."""

    def __init__(
        self,
        workspace: str,
        relative_root: str = ".embedagent/memory/sessions",
    ) -> None:
        self.workspace = os.path.realpath(workspace)
        self.relative_root = relative_root.replace("\\", "/")
        self.root = os.path.join(self.workspace, *self.relative_root.split("/"))

    def load(self, session_id: str) -> Optional[PlanSnapshot]:
        path = self._plan_path(session_id)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (IOError, OSError, ValueError):
            return None
        if not isinstance(payload, dict):
            return None
        return PlanSnapshot(
            session_id=str(payload.get("session_id") or session_id),
            title=str(payload.get("title") or "Current Plan"),
            content=str(payload.get("content") or ""),
            updated_at=str(payload.get("updated_at") or _utc_now()),
            workflow_state=str(payload.get("workflow_state") or "plan"),
            path=self._relative_path(path),
            summary=str(payload.get("summary") or ""),
        )

    def save(
        self,
        session_id: str,
        title: str,
        content: str,
        workflow_state: str = "plan",
        summary: str = "",
    ) -> PlanSnapshot:
        path = self._plan_path(session_id)
        directory = os.path.dirname(path)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        payload = {
            "schema_version": 1,
            "session_id": session_id,
            "title": str(title or "Current Plan"),
            "content": str(content or ""),
            "updated_at": _utc_now(),
            "workflow_state": str(workflow_state or "plan"),
            "summary": str(summary or ""),
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        return PlanSnapshot(
            session_id=session_id,
            title=payload["title"],
            content=payload["content"],
            updated_at=payload["updated_at"],
            workflow_state=payload["workflow_state"],
            path=self._relative_path(path),
            summary=payload["summary"],
        )

    def clear(self, session_id: str) -> None:
        path = self._plan_path(session_id)
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass

    def _plan_path(self, session_id: str) -> str:
        return os.path.join(self.root, session_id, "plan.json")

    def _relative_path(self, absolute_path: str) -> str:
        relative = os.path.relpath(absolute_path, self.workspace)
        return relative.replace(os.sep, "/")
