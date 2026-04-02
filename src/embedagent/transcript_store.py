from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class TranscriptStore(object):
    def __init__(
        self,
        workspace: str,
        relative_root: str = ".embedagent/memory/sessions",
    ) -> None:
        self.workspace = os.path.realpath(workspace)
        self.relative_root = relative_root.replace("\\", "/")
        self.root = os.path.join(self.workspace, *self.relative_root.split("/"))

    def resolve_session_dir(self, session_id: str) -> str:
        if not session_id:
            raise ValueError("session_id is required")
        return os.path.join(self.root, session_id)

    def resolve_transcript_path(self, reference: str) -> str:
        raw = str(reference or "").strip()
        if not raw:
            raise ValueError("transcript reference is required")
        if raw.endswith(".jsonl"):
            candidate = raw if os.path.isabs(raw) else os.path.join(self.workspace, raw)
            return os.path.realpath(candidate)
        return os.path.join(self.resolve_session_dir(raw), "transcript.jsonl")

    def append_event(
        self,
        session_id: str,
        event_type: str,
        payload: Dict[str, Any],
        event_id: str = "",
        ts: str = "",
    ) -> Dict[str, Any]:
        path = self.resolve_transcript_path(session_id)
        directory = os.path.dirname(path)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        seq = self._next_seq(path)
        event = {
            "schema_version": 1,
            "session_id": session_id,
            "event_id": event_id or ("evt-" + uuid.uuid4().hex[:12]),
            "seq": seq,
            "ts": ts or _utc_now(),
            "type": event_type,
            "payload": dict(payload or {}),
        }
        line = json.dumps(event, ensure_ascii=False, sort_keys=True)
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event

    def load_events(self, reference: str) -> List[Dict[str, Any]]:
        path = self.resolve_transcript_path(reference)
        if not os.path.isfile(path):
            raise ValueError("transcript not found: %s" % reference)
        events = []
        last_seq = 0
        with open(path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    break
                if not isinstance(event, dict):
                    break
                seq = int(event.get("seq") or 0)
                if seq <= last_seq:
                    break
                events.append(event)
                last_seq = seq
        return events

    def transcript_exists(self, reference: str) -> bool:
        try:
            path = self.resolve_transcript_path(reference)
        except ValueError:
            return False
        return os.path.isfile(path)

    def _next_seq(self, path: str) -> int:
        if not os.path.isfile(path):
            return 1
        try:
            events = self.load_events(path)
        except ValueError:
            return 1
        if not events:
            return 1
        return int(events[-1].get("seq") or 0) + 1
