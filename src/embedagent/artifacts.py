from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


_OPENAI_KEY_RE = re.compile(r"sk-[A-Za-z0-9_-]{12,}")
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)
_AUTH_HEADER_RE = re.compile(r"(?im)^(Authorization\s*:\s*)(.+)$")
_API_KEY_RE = re.compile(
    r"(?i)((?:api[_-]?key|access[_-]?token|secret|password)\s*[=:]\s*[\"']?)([^\s\"',;]+)"
)


class ArtifactStore(object):
    def __init__(self, workspace: str, relative_root: str = ".embedagent/memory/artifacts") -> None:
        self.workspace = os.path.realpath(workspace)
        self.relative_root = relative_root.replace("\\", "/")
        self.root = os.path.join(self.workspace, *self.relative_root.split("/"))

    def sanitize_text(self, text: str) -> str:
        sanitized = _OPENAI_KEY_RE.sub("<redacted-openai-key>", text)
        sanitized = _BEARER_RE.sub("Bearer <redacted>", sanitized)
        sanitized = _AUTH_HEADER_RE.sub(r"\1<redacted>", sanitized)
        sanitized = _API_KEY_RE.sub(r"\1<redacted>", sanitized)
        return sanitized

    def sanitize_jsonable(self, value: Any) -> Any:
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                result[key] = self.sanitize_jsonable(item)
            return result
        if isinstance(value, list):
            return [self.sanitize_jsonable(item) for item in value]
        if isinstance(value, str):
            return self.sanitize_text(value)
        return value

    def write_text(
        self,
        tool_name: str,
        field_name: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        sanitized = self.sanitize_text(text)
        payload = {
            "schema_version": 1,
            "kind": "text",
            "tool_name": tool_name,
            "field_name": field_name,
            "created_at": _utc_now(),
            "char_count": len(sanitized),
            "line_count": sanitized.count("\n") + (1 if sanitized else 0),
            "metadata": metadata or {},
            "content": sanitized,
        }
        return self._write_payload(tool_name, field_name, payload)

    def write_json(
        self,
        tool_name: str,
        field_name: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        sanitized = self.sanitize_jsonable(value)
        item_count = len(sanitized) if isinstance(sanitized, list) else None
        payload = {
            "schema_version": 1,
            "kind": "json",
            "tool_name": tool_name,
            "field_name": field_name,
            "created_at": _utc_now(),
            "item_count": item_count,
            "metadata": metadata or {},
            "content": sanitized,
        }
        return self._write_payload(tool_name, field_name, payload)

    def _write_payload(self, tool_name: str, field_name: str, payload: Dict[str, Any]) -> str:
        date_segment = datetime.utcnow().strftime("%Y%m%d")
        file_name = "%s-%s-%s.json" % (tool_name, field_name, uuid.uuid4().hex[:12])
        relative_path = os.path.join(self.relative_root.replace("/", os.sep), date_segment, file_name)
        absolute_path = os.path.join(self.workspace, relative_path)
        directory = os.path.dirname(absolute_path)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        with open(absolute_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        return relative_path.replace(os.sep, "/")
