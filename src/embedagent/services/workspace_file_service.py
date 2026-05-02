from __future__ import annotations

import difflib
import io
import logging
import os
from typing import Any, Dict, List, Optional

from embedagent.tools._base import SKIP_DIR_NAMES

logger = logging.getLogger(__name__)


class WorkspaceFileService(object):
    """File operations within workspace boundaries."""

    def __init__(self, workspace_root: str, tool_context: Optional[Any] = None):
        self.workspace_root = workspace_root
        self.tool_context = tool_context

    def resolve_path(self, path: str, allow_missing: bool = False) -> str:
        raw = (path or "").strip()
        if not raw:
            raise ValueError("路径不能为空。")
        candidate = raw if os.path.isabs(raw) else os.path.join(self.workspace_root, raw)
        resolved = os.path.realpath(candidate)
        workspace_norm = os.path.normcase(self.workspace_root)
        resolved_norm = os.path.normcase(resolved)
        if not (
            resolved_norm == workspace_norm
            or resolved_norm.startswith(workspace_norm + os.sep)
        ):
            raise ValueError("路径超出当前工作区。")
        if not allow_missing and not os.path.exists(resolved):
            raise ValueError("路径不存在：%s" % path)
        return resolved

    def relative_path(self, path: str) -> str:
        relative = os.path.relpath(path, self.workspace_root)
        if relative == ".":
            return "."
        return relative.replace(os.sep, "/")

    def read_file(self, path: str) -> Dict[str, Any]:
        candidate = self.resolve_path(path, allow_missing=False)
        if not os.path.isfile(candidate):
            raise ValueError("只能读取文件，不能读取目录。")
        if self.tool_context is not None:
            content, newline, encoding = self.tool_context.read_text(candidate)
        else:
            content, newline, encoding = self._read_text_fallback(candidate)
        return {
            "path": self.relative_path(candidate),
            "encoding": encoding,
            "newline": newline,
            "char_count": len(content),
            "line_count": content.count("\n") + (1 if content else 0),
            "truncated": False,
            "content": content,
        }

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        candidate = self.resolve_path(path, allow_missing=True)
        existed = os.path.isfile(candidate)
        if os.path.isdir(candidate):
            raise ValueError("不能把目录当作文件写入：%s" % path)
        parent = os.path.dirname(candidate)
        if not os.path.isdir(parent):
            os.makedirs(parent)
        newline = "\n"
        encoding = "utf-8"
        old_content = ""
        if existed:
            if self.tool_context is not None:
                old_content, newline, encoding = self.tool_context.read_text(candidate)
            else:
                old_content, newline, encoding = self._read_text_fallback(candidate)
        serialized = str(content or "")
        if self.tool_context is not None:
            self.tool_context.write_text(candidate, serialized, newline, encoding)
        else:
            self._write_text_fallback(candidate, serialized, newline, encoding)
        diff_text = "".join(
            difflib.unified_diff(
                old_content.splitlines(True),
                serialized.splitlines(True),
                fromfile=self.relative_path(candidate),
                tofile=self.relative_path(candidate),
                lineterm="",
            )
        )
        return {
            "path": self.relative_path(candidate),
            "created": not existed,
            "encoding": encoding,
            "newline": newline,
            "char_count": len(serialized),
            "line_count": serialized.count("\n") + (1 if serialized else 0),
            "diff_preview": diff_text,
        }

    def list_directory(
        self,
        path: str = ".",
        limit: int = 200,
    ) -> Dict[str, Any]:
        root = self.resolve_path(path, allow_missing=False)
        if not os.path.isdir(root):
            raise ValueError("路径不是目录：%s" % path)
        items = []  # type: List[Dict[str, Any]]
        try:
            names = sorted(os.listdir(root), key=lambda item: item.lower())
        except OSError:
            names = []
        for name in names:
            absolute = os.path.join(root, name)
            if os.path.isdir(absolute) and name in SKIP_DIR_NAMES:
                continue
            kind = "dir" if os.path.isdir(absolute) else "file"
            items.append(
                {
                    "path": self.relative_path(absolute),
                    "name": name,
                    "kind": kind,
                    "has_children": self._directory_has_visible_children(absolute) if kind == "dir" else False,
                }
            )
            if len(items) >= limit:
                break
        return {"root": self.relative_path(root), "limit": limit, "items": items}

    def list_tree(
        self,
        path: str = ".",
        max_depth: int = 3,
        limit: int = 200,
    ) -> Dict[str, Any]:
        root = self.resolve_path(path, allow_missing=False)
        if not os.path.isdir(root):
            raise ValueError("路径不是目录：%s" % path)
        items = []  # type: List[Dict[str, Any]]
        truncated = [False]

        def walk(current_path: str, depth: int) -> None:
            if truncated[0]:
                return
            try:
                names = sorted(os.listdir(current_path), key=lambda item: item.lower())
            except OSError:
                return
            directories = []
            files = []
            for name in names:
                absolute = os.path.join(current_path, name)
                if os.path.isdir(absolute):
                    if name in SKIP_DIR_NAMES:
                        continue
                    directories.append((name, absolute))
                else:
                    files.append((name, absolute))
            for name, absolute in directories + files:
                items.append(
                    {
                        "path": self.relative_path(absolute),
                        "name": name,
                        "kind": "dir" if os.path.isdir(absolute) else "file",
                        "depth": depth,
                    }
                )
                if len(items) >= limit:
                    truncated[0] = True
                    return
                if os.path.isdir(absolute) and depth < max_depth:
                    walk(absolute, depth + 1)

        walk(root, 0)
        return {
            "root": self.relative_path(root),
            "max_depth": max_depth,
            "limit": limit,
            "truncated": truncated[0],
            "items": items,
        }

    def count_items(self) -> Dict[str, int]:
        file_count = 0
        dir_count = 0
        for current_root, dir_names, file_names in os.walk(self.workspace_root):
            dir_names[:] = [name for name in dir_names if name not in SKIP_DIR_NAMES]
            dir_count += len(dir_names)
            file_count += len(file_names)
        return {"file_count": file_count, "dir_count": dir_count}

    def _directory_has_visible_children(self, path: str) -> bool:
        try:
            names = os.listdir(path)
        except OSError:
            return False
        for name in names:
            if name in SKIP_DIR_NAMES:
                continue
            return True
        return False

    def _read_text_fallback(self, path: str) -> tuple:
        for encoding in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                with io.open(path, "r", encoding=encoding) as handle:
                    content = handle.read()
                newline = self._detect_newline(path)
                return content, newline, encoding
            except (OSError, ValueError, UnicodeDecodeError):
                continue
        raise ValueError("无法读取文件：%s" % path)

    def _write_text_fallback(self, path: str, content: str, newline: str, encoding: str) -> None:
        with io.open(path, "w", encoding=encoding, newline=newline) as handle:
            handle.write(content)

    def _detect_newline(self, path: str) -> str:
        with io.open(path, "rb") as handle:
            sample = handle.read(4096)
        if b"\r\n" in sample:
            return "\r\n"
        if b"\r" in sample:
            return "\r"
        return "\n"
