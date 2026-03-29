from __future__ import annotations

import difflib
import os
from typing import Dict

from embedagent.frontends.terminal.models import EditorBuffer
from embedagent.frontends.terminal.services.workspace import WorkspaceService


class EditorService(object):
    def __init__(self, workspace_service: WorkspaceService, workspace: str) -> None:
        self.workspace_service = workspace_service
        self.workspace = workspace

    def open_buffer(self, path: str) -> EditorBuffer:
        payload = self.workspace_service.read_file(path)
        candidate = os.path.join(self.workspace, str(payload.get("path") or path).replace("/", os.sep))
        return EditorBuffer(
            path=str(payload.get("path") or path),
            content=str(payload.get("content") or ""),
            original_content=str(payload.get("content") or ""),
            encoding=str(payload.get("encoding") or "utf-8"),
            newline=str(payload.get("newline") or "\n"),
            dirty=False,
            created=False,
            file_mtime=os.path.getmtime(candidate) if os.path.isfile(candidate) else 0.0,
        )

    def save_buffer(self, buffer: EditorBuffer) -> Dict[str, str]:
        warning = ""
        if self.has_external_change(buffer):
            warning = "检测到文件在外部发生变化，已按当前缓冲区内容覆盖保存。"
        result = self.workspace_service.write_file(buffer.path, buffer.content)
        candidate = os.path.join(self.workspace, buffer.path.replace("/", os.sep))
        buffer.original_content = buffer.content
        buffer.dirty = False
        buffer.file_mtime = os.path.getmtime(candidate) if os.path.isfile(candidate) else 0.0
        return {"warning": warning, "diff_preview": str(result.get("diff_preview") or "")}

    def diff_preview(self, buffer: EditorBuffer) -> str:
        if not buffer.dirty:
            return ""
        return "".join(
            difflib.unified_diff(
                buffer.original_content.splitlines(True),
                buffer.content.splitlines(True),
                fromfile=buffer.path,
                tofile=buffer.path,
                lineterm="",
            )
        )

    def has_external_change(self, buffer: EditorBuffer) -> bool:
        if not buffer.path:
            return False
        candidate = os.path.join(self.workspace, buffer.path.replace("/", os.sep))
        if not os.path.isfile(candidate):
            return False
        if buffer.file_mtime <= 0:
            return False
        return os.path.getmtime(candidate) > buffer.file_mtime
