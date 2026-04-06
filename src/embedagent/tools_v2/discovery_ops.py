from __future__ import annotations

import fnmatch
import os
from typing import Any, Dict, List

from embedagent.session import Observation
from embedagent.tools._base import ToolDefinition


def build_tools(ctx) -> List[ToolDefinition]:
    def _list_dir(arguments: Dict[str, Any]) -> Observation:
        path = ctx.resolve_directory(str(arguments.get("path") or "."))
        limit = max(1, int(arguments.get("limit") or 50))
        offset = max(0, int(arguments.get("offset") or 0))
        names = sorted(os.listdir(path), key=lambda item: item.lower())
        items = []
        for name in names[offset : offset + limit]:
            candidate = os.path.join(path, name)
            label = name + ("/" if os.path.isdir(candidate) else "")
            items.append(label)
        return Observation(
            tool_name="list_dir",
            success=True,
            error=None,
            data={
                "preview": items,
                "returned_count": len(items),
                "total_count": len(names),
                "has_more": offset + len(items) < len(names),
                "next_offset": offset + len(items),
                "result_ref": "",
            },
        )

    def _glob_files(arguments: Dict[str, Any]) -> Observation:
        pattern = str(arguments.get("pattern") or "").strip()
        path = ctx.resolve_directory(str(arguments.get("path") or "."))
        limit = max(1, int(arguments.get("limit") or 50))
        offset = max(0, int(arguments.get("offset") or 0))
        matches = []
        for absolute_path in ctx.iter_files(path, pattern=None):
            relative = ctx.relative_path(absolute_path)
            if fnmatch.fnmatch(os.path.basename(relative), pattern) or fnmatch.fnmatch(relative, pattern):
                matches.append(relative)
        items = matches[offset : offset + limit]
        return Observation(
            tool_name="glob_files",
            success=True,
            error=None,
            data={
                "preview": items,
                "returned_count": len(items),
                "total_count": len(matches),
                "has_more": offset + len(items) < len(matches),
                "next_offset": offset + len(items),
                "result_ref": "",
            },
        )

    def _grep_text(arguments: Dict[str, Any]) -> Observation:
        pattern = str(arguments.get("pattern") or "").strip()
        path = ctx.resolve_directory(str(arguments.get("path") or "."))
        limit = max(1, int(arguments.get("limit") or 20))
        offset = max(0, int(arguments.get("offset") or 0))
        matches = []
        lowered = pattern.lower()
        for absolute_path in ctx.iter_files(path, pattern=None):
            if ctx.is_binary_file(absolute_path):
                continue
            try:
                content, _, _ = ctx.read_text(absolute_path)
            except Exception:
                continue
            for line_number, line_text in enumerate(content.split("\n"), start=1):
                if lowered and lowered not in line_text.lower():
                    continue
                matches.append(
                    "%s:%s:%s" % (
                        ctx.relative_path(absolute_path),
                        line_number,
                        line_text[:200],
                    )
                )
        items = matches[offset : offset + limit]
        return Observation(
            tool_name="grep_text",
            success=True,
            error=None,
            data={
                "preview": items,
                "returned_count": len(items),
                "total_count": len(matches),
                "has_more": offset + len(items) < len(matches),
                "next_offset": offset + len(items),
                "result_ref": "",
            },
        )

    return [
        ToolDefinition(
            name="list_dir",
            description="列出目录的一层内容。用于轻量查看当前目录结构。支持 limit 和 offset 分页。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径。示例：src"},
                    "limit": {"type": "integer", "description": "返回数量上限。示例：50"},
                    "offset": {"type": "integer", "description": "分页偏移。示例：0"},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=_list_dir,
            read_only=True,
            concurrency_safe=True,
        ),
        ToolDefinition(
            name="glob_files",
            description="按文件名或路径模式查找文件。用于替代递归 list_files。支持 limit 和 offset 分页。",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "glob 模式。示例：**/*.c"},
                    "path": {"type": "string", "description": "搜索根目录。示例：src"},
                    "limit": {"type": "integer", "description": "返回数量上限。示例：50"},
                    "offset": {"type": "integer", "description": "分页偏移。示例：0"},
                },
                "required": ["pattern", "path"],
                "additionalProperties": False,
            },
            handler=_glob_files,
            read_only=True,
            concurrency_safe=True,
        ),
        ToolDefinition(
            name="grep_text",
            description="按文本模式搜索内容。用于定位符号、关键字和错误文本。支持 limit 和 offset 分页。",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "搜索文本。示例：demo"},
                    "path": {"type": "string", "description": "搜索根目录。示例：src"},
                    "limit": {"type": "integer", "description": "返回数量上限。示例：20"},
                    "offset": {"type": "integer", "description": "分页偏移。示例：0"},
                },
                "required": ["pattern", "path"],
                "additionalProperties": False,
            },
            handler=_grep_text,
            read_only=True,
            concurrency_safe=True,
        ),
    ]
