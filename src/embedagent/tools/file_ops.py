from __future__ import annotations

import os
from typing import Any, Dict, List

from embedagent.session import Observation
from embedagent.tools._base import (
    MAX_READ_CHARS,
    MAX_LIST_RESULTS,
    MAX_SEARCH_MATCHES,
    ToolContext,
    ToolDefinition,
    ToolError,
)


def build_tools(ctx: ToolContext) -> List[ToolDefinition]:

    def _read_file(arguments: Dict[str, Any]) -> Observation:
        path = ctx.resolve_path(str(arguments["path"]))
        if not os.path.isfile(path):
            raise ToolError("只能读取文件，不能读取目录。")
        content, _, encoding = ctx.read_text(path)
        original_length = len(content)
        truncated = original_length > MAX_READ_CHARS
        if truncated:
            content = content[:MAX_READ_CHARS]
        data = {
            "path": ctx.relative_path(path),
            "encoding": encoding,
            "char_count": original_length,
            "line_count": content.count("\n") + (1 if content else 0),
            "truncated": truncated,
            "content": content,
        }
        return Observation(tool_name="read_file", success=True, error=None, data=data)

    def _list_files(arguments: Dict[str, Any]) -> Observation:
        path = ctx.resolve_path(str(arguments["path"]))
        pattern = arguments.get("pattern")
        pattern = str(pattern) if pattern else None
        files = ctx.iter_files(path, pattern)
        truncated = len(files) > MAX_LIST_RESULTS
        visible = files[:MAX_LIST_RESULTS]
        data = {
            "path": ctx.relative_path(path),
            "pattern": pattern,
            "count": len(files),
            "truncated": truncated,
            "files": [ctx.relative_path(item) for item in visible],
        }
        return Observation(tool_name="list_files", success=True, error=None, data=data)

    def _search_text(arguments: Dict[str, Any]) -> Observation:
        query = str(arguments["query"])
        path = ctx.resolve_path(str(arguments["path"]))
        if not query:
            raise ToolError("搜索文本不能为空。")
        matches = []
        lowered_query = query.lower()
        for file_path in ctx.iter_files(path, pattern=None):
            if ctx.is_binary_file(file_path):
                continue
            try:
                content, _, _ = ctx.read_text(file_path)
            except ToolError:
                continue
            for index, line in enumerate(content.split("\n"), start=1):
                if lowered_query not in line.lower():
                    continue
                matches.append({"path": ctx.relative_path(file_path), "line": index, "text": line[:300]})
                if len(matches) >= MAX_SEARCH_MATCHES:
                    break
            if len(matches) >= MAX_SEARCH_MATCHES:
                break
        data = {
            "query": query,
            "path": ctx.relative_path(path),
            "match_count": len(matches),
            "truncated": len(matches) >= MAX_SEARCH_MATCHES,
            "matches": matches,
        }
        return Observation(tool_name="search_text", success=True, error=None, data=data)

    def _edit_file(arguments: Dict[str, Any]) -> Observation:
        path = ctx.resolve_path(str(arguments["path"]))
        if not os.path.isfile(path):
            raise ToolError("只能修改已存在的文本文件。")
        old_text = str(arguments["old_text"])
        new_text = str(arguments["new_text"])
        if not old_text:
            raise ToolError("old_text 不能为空。")
        content, newline_style, encoding = ctx.read_text(path)
        occurrence_count = content.count(old_text)
        if occurrence_count == 0:
            raise ToolError("文件中未找到要替换的原始文本。")
        if occurrence_count > 1:
            raise ToolError("原始文本出现了 %s 次，请提供更精确的片段。" % occurrence_count)
        updated = content.replace(old_text, new_text, 1)
        ctx.write_text(path, updated, newline_style, encoding)
        data = {
            "path": ctx.relative_path(path),
            "encoding": encoding,
            "replaced": True,
            "line_count": updated.count("\n") + (1 if updated else 0),
        }
        return Observation(tool_name="edit_file", success=True, error=None, data=data)

    return [
        ToolDefinition(
            name="read_file",
            description="读取单个文本文件内容。用于查看源码、配置或文档的当前状态。路径必须位于项目工作区内。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要读取的文件路径，相对于项目根目录。示例：README.md",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=_read_file,
        ),
        ToolDefinition(
            name="list_files",
            description="列出目录中的文件路径。用于快速了解项目结构或定位目标文件。路径必须位于项目工作区内。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要列出的目录路径，相对于项目根目录。示例：docs",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "要匹配的 glob 模式，留空表示不过滤。示例：*.md",
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=_list_files,
        ),
        ToolDefinition(
            name="search_text",
            description="搜索工作区中的文本内容。用于查找符号、关键字或错误信息出现位置。路径必须位于项目工作区内。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要搜索的文本片段，默认按不区分大小写匹配。示例：OpenAICompatibleClient",
                    },
                    "path": {
                        "type": "string",
                        "description": "要搜索的目录路径，相对于项目根目录。示例：src/embedagent",
                    },
                },
                "required": ["query", "path"],
                "additionalProperties": False,
            },
            handler=_search_text,
        ),
        ToolDefinition(
            name="edit_file",
            description="修改文件中的指定文本片段。用于替换、插入或删除已存在的内容。路径必须位于项目工作区内。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要修改的文件路径，相对于项目根目录。示例：src/embedagent/loop.py",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "要被替换的原始文本，必须与文件内容完全一致。示例：print('old')",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "替换后的新文本，传入空字符串表示删除。示例：print('new')",
                    },
                },
                "required": ["path", "old_text", "new_text"],
                "additionalProperties": False,
            },
            handler=_edit_file,
        ),
    ]
