from __future__ import annotations

import fnmatch
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from embedagent_core.session import Observation
from embedagent_core.tool_contracts import ToolDefinition, ToolError, diagnostic_tool_error

from embedagent_host.runtime.constants import SKIP_DIR_NAMES, SKIP_RELATIVE_DIRS


def _resolve_search_root(ctx, raw_path: str) -> str:
    try:
        return ctx.resolve_path(raw_path)
    except ToolError as exc:
        text = str(exc)
        if "路径不存在" in text:
            raise diagnostic_tool_error(
                text,
                "path_not_found",
                "Use list_dir or glob_files to find the correct search root.",
            )
        if "路径超出当前工作区" in text:
            raise diagnostic_tool_error(
                text,
                "path_outside_workspace",
                "Search only paths inside the current workspace.",
            )
        raise


def _resolve_listing_directory(ctx, raw_path: str) -> str:
    try:
        return ctx.resolve_directory(raw_path)
    except ToolError as exc:
        text = str(exc)
        if "路径不存在" in text:
            raise diagnostic_tool_error(
                text,
                "path_not_found",
                "Use list_dir or glob_files to find an existing directory.",
            )
        if "路径超出当前工作区" in text:
            raise diagnostic_tool_error(
                text,
                "path_outside_workspace",
                "List only paths inside the current workspace.",
            )
        if "路径不是目录" in text:
            raise diagnostic_tool_error(
                text,
                "not_directory",
                "Use read_file for files or choose a directory path.",
            )
        raise


def _compile_pattern(pattern: str, literal: bool):
    if literal:
        return None
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise diagnostic_tool_error(
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


def _normalize_preview_path(path: str) -> str:
    return str(path or "").replace("\\", "/")


def _is_regex_parse_error(stderr: str) -> bool:
    text = str(stderr or "").lower()
    return "regex parse error" in text or "regex parse" in text


def _parse_rg_line(line: str) -> Optional[Tuple[str, int, str]]:
    parts = str(line or "").split(":", 2)
    if len(parts) != 3:
        return None
    try:
        line_number = int(parts[1])
    except ValueError:
        return None
    return _normalize_preview_path(parts[0]), line_number, parts[2]


def _skip_globs() -> Iterable[str]:
    for name in sorted(SKIP_DIR_NAMES):
        yield "%s/**" % name
    for relative_path in sorted(SKIP_RELATIVE_DIRS):
        yield "%s/**" % relative_path


def build_tools(ctx) -> List[ToolDefinition]:
    def _list_dir(arguments: Dict[str, Any]) -> Observation:
        path = _resolve_listing_directory(ctx, str(arguments.get("path") or "."))
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
        path = _resolve_listing_directory(ctx, str(arguments.get("path") or "."))
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

    def _grep_text_with_python(
        pattern: str,
        path: str,
        limit: int,
        offset: int,
        literal: bool,
    ) -> Tuple[List[str], int, Dict[str, Any]]:
        matches = []
        decode_error_count = 0
        lowered = pattern.lower()
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
        return (
            matches[offset : offset + limit],
            len(matches),
            {"decode_error_count": decode_error_count, "search_backend": "python"},
        )

    def _grep_text_with_rg(
        pattern: str,
        path: str,
        limit: int,
        offset: int,
        literal: bool,
    ) -> Optional[Tuple[List[str], int, Dict[str, Any]]]:
        rg_exe, rg_source = ctx.resolve_managed_tool_path("rg")
        if not rg_exe:
            return None
        command = [
            rg_exe,
            "--line-number",
            "--with-filename",
            "--color",
            "never",
            "--hidden",
            "--no-ignore",
            "--ignore-case",
            "--encoding",
            "auto",
            "--max-count",
            str(offset + limit + 1),
        ]
        if literal:
            command.append("--fixed-strings")
        for skip_glob in _skip_globs():
            command.extend(["--glob", "!%s" % skip_glob])
        command.extend(["--", pattern, ctx.relative_path(path)])
        try:
            result = ctx.run_subprocess(
                command=command,
                cwd=ctx.workspace,
                timeout_sec=10,
                shell=False,
                stop_event=ctx.get_interrupt_event(),
            )
        except OSError as exc:
            raise diagnostic_tool_error(
                "ripgrep 搜索失败：%s" % exc,
                "search_failed",
                "Check the bundled ripgrep executable and retry.",
            )
        exit_code = int(result.get("exit_code") or 0)
        stderr = str(result.get("stderr") or "")
        if exit_code not in (0, 1):
            if _is_regex_parse_error(stderr):
                raise diagnostic_tool_error(
                    "搜索模式不是有效正则表达式：%s" % stderr.strip(),
                    "invalid_pattern",
                    "Set literal=true for fixed-string search or provide a valid regular expression.",
                )
            raise diagnostic_tool_error(
                "ripgrep 搜索失败：%s" % (stderr.strip() or "exit code %s" % exit_code),
                "search_failed",
                "Check the search path and pattern, then retry with a narrower query.",
            )
        parsed = []
        for line in str(result.get("stdout") or "").splitlines():
            parsed_line = _parse_rg_line(line)
            if parsed_line is None:
                continue
            file_path, line_number, line_text = parsed_line
            parsed.append("%s:%s:%s" % (file_path, line_number, line_text[:200]))
        items = parsed[offset : offset + limit]
        return (
            items,
            len(parsed) if exit_code == 0 else 0,
            {
                "decode_error_count": int(result.get("stdout_decode_errors_count") or 0)
                + int(result.get("stderr_decode_errors_count") or 0),
                "search_backend": "rg",
                "managed_tool_source": rg_source,
                "has_more": exit_code == 0 and len(parsed) > offset + limit,
            },
        )

    def _grep_text(arguments: Dict[str, Any]) -> Observation:
        pattern = str(arguments.get("pattern") or "").strip()
        path = _resolve_search_root(ctx, str(arguments.get("path") or "."))
        limit = max(1, int(arguments.get("limit") or 20))
        offset = max(0, int(arguments.get("offset") or 0))
        literal = bool(arguments.get("literal", False))
        result = _grep_text_with_rg(pattern, path, limit, offset, literal)
        if result is None:
            result = _grep_text_with_python(pattern, path, limit, offset, literal)
        items, total_count, metadata = result
        has_more = bool(metadata.pop("has_more", offset + len(items) < total_count))
        return Observation(
            tool_name="grep_text",
            success=True,
            error=None,
            data={
                "preview": items,
                "returned_count": len(items),
                "total_count": total_count,
                "has_more": has_more,
                "next_offset": offset + len(items),
                "result_ref": "",
                "decode_error_count": int(metadata.get("decode_error_count") or 0),
                "search_backend": metadata.get("search_backend") or "python",
                "managed_tool_source": metadata.get("managed_tool_source") or "",
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
