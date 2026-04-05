from __future__ import annotations

import io
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Set

from embedagent.persistence_sanitize import sanitize_jsonable, sanitize_text


_PREVIEW_LIMIT = 1600
_LOGGER = logging.getLogger(__name__)


@dataclass
class StoredToolResultField:
    session_id: str
    tool_call_id: str
    field_name: str
    content_kind: str
    absolute_path: str
    relative_path: str
    byte_count: int
    line_count: int
    preview_text: str


class ToolResultStore(object):
    def __init__(
        self,
        workspace: str,
        relative_root: str = ".embedagent/memory/sessions",
    ) -> None:
        self.workspace = os.path.realpath(workspace)
        self.relative_root = relative_root.replace("\\", "/")
        self.root = os.path.join(self.workspace, *self.relative_root.split("/"))

    def _preview(self, text: str, limit: int = _PREVIEW_LIMIT) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "\n...[stored preview truncated]"

    def _field_path(
        self,
        session_id: str,
        tool_call_id: str,
        field_name: str,
        extension: str,
    ) -> str:
        return os.path.join(
            self.root,
            session_id,
            "tool-results",
            tool_call_id,
            "%s.%s" % (field_name, extension),
        )

    def _ensure_parent(self, path: str) -> None:
        parent = os.path.dirname(path)
        if not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)

    def _write_if_absent(self, path: str, text: str) -> None:
        self._ensure_parent(path)
        try:
            with io.open(path, "x", encoding="utf-8", newline="") as handle:
                handle.write(text)
        except FileExistsError:
            try:
                with io.open(path, "r", encoding="utf-8") as handle:
                    existing = handle.read()
            except OSError:
                _LOGGER.debug("tool result already existed and could not be re-read: %s", path)
                return
            if existing == text:
                _LOGGER.debug("duplicate tool result materialization ignored for %s", path)
            else:
                _LOGGER.debug("tool result path already exists with different content: %s", path)
            return

    def _build_record(
        self,
        session_id: str,
        tool_call_id: str,
        field_name: str,
        content_kind: str,
        path: str,
        serialized: str,
    ) -> StoredToolResultField:
        return StoredToolResultField(
            session_id=session_id,
            tool_call_id=tool_call_id,
            field_name=field_name,
            content_kind=content_kind,
            absolute_path=path,
            relative_path=os.path.relpath(path, self.workspace).replace(os.sep, "/"),
            byte_count=len(serialized.encode("utf-8")),
            line_count=serialized.count("\n") + (1 if serialized else 0),
            preview_text=self._preview(serialized),
        )

    def write_text(
        self,
        session_id: str,
        tool_call_id: str,
        field_name: str,
        text: Any,
    ) -> StoredToolResultField:
        sanitized = sanitize_text(text)
        path = self._field_path(session_id, tool_call_id, field_name, "txt")
        self._write_if_absent(path, sanitized)
        return self._build_record(
            session_id,
            tool_call_id,
            field_name,
            "text",
            path,
            sanitized,
        )

    def write_json(
        self,
        session_id: str,
        tool_call_id: str,
        field_name: str,
        value: Any,
    ) -> StoredToolResultField:
        serialized = json.dumps(
            sanitize_jsonable(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        path = self._field_path(session_id, tool_call_id, field_name, "json")
        self._write_if_absent(path, serialized)
        return self._build_record(
            session_id,
            tool_call_id,
            field_name,
            "json",
            path,
            serialized,
        )

    def resolve_existing_path(self, reference: str) -> str:
        raw = (reference or "").strip()
        if not raw:
            raise ValueError("stored path 不能为空。")
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
            raise ValueError("stored path 超出 sessions 根目录。")
        if not os.path.isfile(candidate):
            raise ValueError("stored file 不存在：%s" % reference)
        return candidate

    def cleanup_unreferenced(self, active_paths: Iterable[str]) -> dict:
        normalized_active = set()  # type: Set[str]
        for path in active_paths or []:
            if path:
                normalized_active.add(str(path).replace("\\", "/"))
        deleted = 0
        kept = 0
        if not os.path.isdir(self.root):
            return {"kept": kept, "deleted": deleted}
        for session_name in os.listdir(self.root):
            tool_results_root = os.path.join(self.root, session_name, "tool-results")
            if not os.path.isdir(tool_results_root):
                continue
            for current_root, _, file_names in os.walk(tool_results_root):
                for file_name in file_names:
                    absolute = os.path.join(current_root, file_name)
                    relative = os.path.relpath(absolute, self.workspace).replace(os.sep, "/")
                    if relative in normalized_active:
                        kept += 1
                        continue
                    os.remove(absolute)
                    deleted += 1
        return {"kept": kept, "deleted": deleted}
