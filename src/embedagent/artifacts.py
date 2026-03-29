from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _atomic_write_json(path: str, payload: Any) -> None:
    """Write *payload* as JSON to *path* atomically via temp-file rename."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)


_OPENAI_KEY_RE = re.compile(r"sk-[A-Za-z0-9_-]{12,}")
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)
_AUTH_HEADER_RE = re.compile(r"(?im)^(Authorization\s*:\s*)(.+)$")
_API_KEY_RE = re.compile(
    r"(?i)((?:api[_-]?key|access[_-]?token|secret|password)\s*[=:]\s*[\"']?)([^\s\"',;]+)"
)


class ArtifactStore(object):
    def __init__(self, workspace: str, relative_root: str = ".embedagent/memory/artifacts", max_index_entries: int = 512) -> None:
        self.workspace = os.path.realpath(workspace)
        self.relative_root = relative_root.replace("\\", "/")
        self.root = os.path.join(self.workspace, *self.relative_root.split("/"))
        self.index_path = os.path.join(self.root, "index.json")
        self.max_index_entries = max_index_entries

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


    def list_artifacts(self, limit: int = 20) -> List[Dict[str, Any]]:
        index = self._read_index()
        items = index.get("artifacts") if isinstance(index.get("artifacts"), list) else []
        result = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            result.append(item)
        return result

    def resolve_artifact_path(self, reference: str) -> str:
        raw = self._normalize_ref((reference or "").strip())
        if not raw:
            raise ValueError("artifact 引用不能为空。")
        candidate = raw
        if not os.path.isabs(candidate):
            candidate = os.path.join(self.workspace, candidate.replace("/", os.sep))
        candidate = os.path.realpath(candidate)
        root_norm = os.path.normcase(self.root)
        candidate_norm = os.path.normcase(candidate)
        if not (
            candidate_norm == root_norm
            or candidate_norm.startswith(root_norm + os.sep)
        ):
            raise ValueError("artifact 路径超出 artifacts 根目录。")
        if not os.path.isfile(candidate):
            raise ValueError("artifact 不存在：%s" % reference)
        return candidate

    def read_artifact(self, reference: str) -> Dict[str, Any]:
        artifact_path = self.resolve_artifact_path(reference)
        with open(artifact_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("artifact 内容不可用：%s" % reference)
        payload["path"] = os.path.relpath(artifact_path, self.workspace).replace(os.sep, "/")
        return payload

    def cleanup(
        self,
        active_refs: Optional[object] = None,
        max_entries: int = 256,
        max_age_days: int = 14,
    ) -> Dict[str, int]:
        index = self._read_index()
        artifacts = index.get("artifacts") if isinstance(index.get("artifacts"), list) else []
        normalized_active = set()
        for item in active_refs or []:
            normalized_active.add(self._normalize_ref(str(item)))
        threshold = datetime.utcnow() - timedelta(days=max_age_days)
        kept = []
        deleted = 0
        seen = set()
        sorted_items = sorted(artifacts, key=lambda item: item.get("created_at") or "", reverse=True)
        for position, item in enumerate(sorted_items):
            if not isinstance(item, dict):
                continue
            path = self._normalize_ref(str(item.get("path") or ""))
            if not path or path in seen:
                continue
            seen.add(path)
            absolute_path = os.path.join(self.workspace, path.replace("/", os.sep))
            if not os.path.isfile(absolute_path):
                deleted += 1
                continue
            created_at = self._parse_time(item.get("created_at"))
            keep = path in normalized_active or position < max_entries
            if created_at is not None and created_at >= threshold:
                keep = True
            if keep:
                item["path"] = path
                kept.append(item)
                continue
            try:
                os.remove(absolute_path)
                deleted += 1
            except OSError:
                item["path"] = path
                kept.append(item)
        payload = {
            "schema_version": 1,
            "updated_at": _utc_now(),
            "artifacts": kept[: self.max_index_entries],
        }
        self._write_index(payload)
        return {"kept": len(payload["artifacts"]), "deleted": deleted}

    def _update_index(self, relative_ref: str, payload: Dict[str, Any]) -> None:
        index = self._read_index()
        artifacts = index.get("artifacts") if isinstance(index.get("artifacts"), list) else []
        record = {
            "path": self._normalize_ref(relative_ref),
            "tool_name": payload.get("tool_name"),
            "field_name": payload.get("field_name"),
            "kind": payload.get("kind"),
            "created_at": payload.get("created_at") or _utc_now(),
            "char_count": payload.get("char_count"),
            "item_count": payload.get("item_count"),
        }
        updated = [item for item in artifacts if item.get("path") != record["path"]]
        updated.append(record)
        updated.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        self._write_index({
            "schema_version": 1,
            "updated_at": _utc_now(),
            "artifacts": updated[: self.max_index_entries],
        })

    def _read_index(self) -> Dict[str, Any]:
        if not os.path.isfile(self.index_path):
            return {}
        try:
            with open(self.index_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _write_index(self, payload: Dict[str, Any]) -> None:
        if not os.path.isdir(self.root):
            os.makedirs(self.root)
        _atomic_write_json(self.index_path, payload)

    def _normalize_ref(self, reference: str) -> str:
        return reference.replace("\\", "/")

    def _parse_time(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return None
    def _write_payload(self, tool_name: str, field_name: str, payload: Dict[str, Any]) -> str:
        date_segment = datetime.utcnow().strftime("%Y%m%d")
        file_name = "%s-%s-%s.json" % (tool_name, field_name, uuid.uuid4().hex[:12])
        relative_path = os.path.join(self.relative_root.replace("/", os.sep), date_segment, file_name)
        absolute_path = os.path.join(self.workspace, relative_path)
        directory = os.path.dirname(absolute_path)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        _atomic_write_json(absolute_path, payload)
        relative_ref = relative_path.replace(os.sep, "/")
        self._update_index(relative_ref, payload)
        return relative_ref


