from __future__ import annotations

import difflib
import os
from typing import Any, Dict, List

from embedagent.tools._base import SKIP_DIR_NAMES, TEXT_ENCODINGS


class WorkspaceService(object):
    def __init__(self, adapter, workspace: str) -> None:
        self.adapter = adapter
        self.workspace = os.path.realpath(workspace)

    def snapshot(self) -> Dict[str, Any]:
        method = getattr(self.adapter, "get_workspace_snapshot", None)
        if callable(method):
            try:
                return method()
            except Exception:
                pass
        file_count = 0
        dir_count = 0
        for current_root, dir_names, file_names in os.walk(self.workspace):
            dir_names[:] = [name for name in dir_names if name not in SKIP_DIR_NAMES]
            file_count += len(file_names)
            dir_count += len(dir_names)
        return {
            "workspace": self.workspace,
            "git": {"available": False, "branch": "", "dirty_count": 0, "modified_count": 0, "untracked_count": 0},
            "tree": {"file_count": file_count, "dir_count": dir_count},
        }

    def tree(self, path: str = ".", max_depth: int = 3, limit: int = 200) -> Dict[str, Any]:
        method = getattr(self.adapter, "list_workspace_tree", None)
        if callable(method):
            try:
                return method(path=path, max_depth=max_depth, limit=limit)
            except Exception:
                pass
        root = self._resolve(path)
        items = []
        truncated = [False]

        def walk(current_path: str, depth: int) -> None:
            if truncated[0]:
                return
            try:
                names = sorted(os.listdir(current_path), key=lambda item: item.lower())
            except OSError:
                return
            for name in names:
                absolute = os.path.join(current_path, name)
                if os.path.isdir(absolute) and name in SKIP_DIR_NAMES:
                    continue
                items.append({
                    "path": self._relative(absolute),
                    "name": name,
                    "kind": "dir" if os.path.isdir(absolute) else "file",
                    "depth": depth,
                })
                if len(items) >= limit:
                    truncated[0] = True
                    return
                if os.path.isdir(absolute) and depth < max_depth:
                    walk(absolute, depth + 1)

        if os.path.isdir(root):
            walk(root, 0)
        return {"root": self._relative(root), "max_depth": max_depth, "limit": limit, "truncated": truncated[0], "items": items}

    def read_file(self, path: str) -> Dict[str, Any]:
        method = getattr(self.adapter, "read_workspace_file", None)
        if callable(method):
            try:
                return method(path)
            except Exception:
                pass
        candidate = self._resolve(path)
        raw = open(candidate, "rb").read()
        encoding = "utf-8"
        for candidate_encoding in TEXT_ENCODINGS:
            try:
                text = raw.decode(candidate_encoding)
                encoding = candidate_encoding
                break
            except UnicodeDecodeError:
                text = raw.decode("utf-8", errors="replace")
        newline = "\r\n" if b"\r\n" in raw else ("\r" if b"\r" in raw else "\n")
        return {
            "path": self._relative(candidate),
            "encoding": encoding,
            "newline": newline,
            "char_count": len(text),
            "line_count": text.count("\n") + (1 if text else 0),
            "truncated": False,
            "content": text,
        }

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        method = getattr(self.adapter, "write_workspace_file", None)
        if callable(method):
            return method(path, content)
        candidate = self._resolve(path, allow_missing=True)
        existed = os.path.isfile(candidate)
        old_text = ""
        encoding = "utf-8"
        newline = "\n"
        if existed:
            loaded = self.read_file(path)
            old_text = str(loaded.get("content") or "")
            encoding = str(loaded.get("encoding") or "utf-8")
            newline = str(loaded.get("newline") or "\n")
        parent = os.path.dirname(candidate)
        if not os.path.isdir(parent):
            os.makedirs(parent)
        with open(candidate, "w", encoding=encoding, newline="") as handle:
            handle.write(str(content or "").replace("\n", newline))
        diff_text = "".join(
            difflib.unified_diff(
                old_text.splitlines(True),
                str(content or "").splitlines(True),
                fromfile=self._relative(candidate),
                tofile=self._relative(candidate),
                lineterm="",
            )
        )
        return {
            "path": self._relative(candidate),
            "created": not existed,
            "encoding": encoding,
            "newline": newline,
            "char_count": len(str(content or "")),
            "line_count": str(content or "").count("\n") + (1 if content else 0),
            "diff_preview": diff_text,
        }

    def _resolve(self, path: str, allow_missing: bool = False) -> str:
        raw = (path or ".").strip()
        candidate = raw if os.path.isabs(raw) else os.path.join(self.workspace, raw)
        resolved = os.path.realpath(candidate)
        workspace_norm = os.path.normcase(self.workspace)
        resolved_norm = os.path.normcase(resolved)
        if not (resolved_norm == workspace_norm or resolved_norm.startswith(workspace_norm + os.sep)):
            raise ValueError("路径超出当前工作区。")
        if not allow_missing and not os.path.exists(resolved):
            raise ValueError("路径不存在：%s" % path)
        return resolved

    def _relative(self, path: str) -> str:
        relative = os.path.relpath(path, self.workspace)
        if relative == ".":
            return "."
        return relative.replace(os.sep, "/")
