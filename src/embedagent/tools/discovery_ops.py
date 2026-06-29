from __future__ import annotations

import fnmatch
import os
import re
from typing import Any, Dict, List

from embedagent.session import Observation
from embedagent.tools._base import ToolDefinition, ToolError


def _diagnostic_tool_error(message: str, error_kind: str, suggested_next_step: str = "") -> ToolError:
    return ToolError(
        message,
        error_kind=error_kind,
        retryable=False,
        outcome_class="diagnostic_failure",
        suggested_next_step=suggested_next_step,
    )


def _resolve_search_root(ctx, raw_path: str) -> str:
    try:
        return ctx.resolve_path(raw_path)
    except ToolError as exc:
        text = str(exc)
        if "路径不存在" in text:
            raise _diagnostic_tool_error(
                text,
                "path_not_found",
                "Use list_dir or glob_files to find the correct search root.",
            )
        if "路径超出当前工作区" in text:
            raise _diagnostic_tool_error(
                text,
                "path_outside_workspace",
                "Search only paths inside the current workspace.",
            )
        raise


def _compile_pattern(pattern: str, literal: bool):
    if literal:
        return None
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise _diagnostic_tool_error(
            "搜索模式不是有效正则表达式：%s" % exc,
            "invalid_pattern",
            "Set literal=true for fixed-string search or provide a valid regular expression.",
        )


def _line_matches(line_text: str, lowered_pattern: str, compiled_pattern, literal: bool) -> bool:
    if not lowered_pattern:
        return True
    if literal:
        return lowered_pattern in line_text.lower()
    return compiled_pattern.search(line_text) is not None


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
            if fnmatch.fnmatch(os.path.basename(relative), pattern) or fnmatch.fnmatch(
                relative, pattern
            ):
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
        path = _resolve_search_root(ctx, str(arguments.get("path") or "."))
        limit = max(1, int(arguments.get("limit") or 20))
        offset = max(0, int(arguments.get("offset") or 0))
        matches = []
        decode_error_count = 0
        lowered = pattern.lower()
        literal = bool(arguments.get("literal", False))
        compiled_pattern = _compile_pattern(pattern, literal)
        for absolute_path in ctx.iter_files(path, pattern=None):
            if ctx.is_binary_file(absolute_path):
                continue
            try:
                content, _, encoding = ctx.read_text(absolute_path)
            except (OSError, ToolError, UnicodeDecodeError, ValueError):
                continue
            if str(encoding or "").endswith("-replace"):
                decode_error_count += 1
            for line_number, line_text in enumerate(content.split("\n"), start=1):
                if not _line_matches(line_text, lowered, compiled_pattern, literal):
                    continue
                matches.append(
                    "%s:%s:%s"
                    % (
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
                "decode_error_count": decode_error_count,
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
            description="按文件名或路径模式查找文件。用于按需收窄候选文件范围。支持 limit 和 offset 分页。",
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
                    "literal": {
                        "type": "boolean",
                        "description": "为 true 时按固定字符串搜索；默认为 false，按正则表达式搜索。",
                    },
                },
                "required": ["pattern", "path"],
                "additionalProperties": False,
            },
            handler=_grep_text,
            read_only=True,
            concurrency_safe=True,
        ),
    ]
