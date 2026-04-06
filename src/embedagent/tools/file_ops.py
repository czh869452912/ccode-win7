from __future__ import annotations

import os
from typing import Any, Dict, List

from embedagent.session import Observation
from embedagent.tools._base import MAX_READ_CHARS, ToolContext, ToolDefinition, ToolError


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

    def _write_file(arguments: Dict[str, Any]) -> Observation:
        path = ctx.resolve_path(str(arguments["path"]), allow_missing=True)
        if os.path.isdir(path):
            raise ToolError("不能把目录当作文件写入。")
        overwrite = bool(arguments.get("overwrite", False))
        existed = os.path.isfile(path)
        if existed and not overwrite:
            raise ToolError("目标文件已存在；如需整体覆盖，请把 overwrite 设为 true。")
        content = str(arguments.get("content") or "")
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        newline_style = "\n"
        encoding = "utf-8"
        if existed:
            _, newline_style, encoding = ctx.read_text(path)
        ctx.write_text(path, content, newline_style, encoding)
        data = {
            "path": ctx.relative_path(path),
            "created": not existed,
            "overwritten": existed,
            "encoding": encoding,
            "char_count": len(content),
            "line_count": content.count("\n") + (1 if content else 0),
        }
        return Observation(tool_name="write_file", success=True, error=None, data=data)

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
            name="write_file",
            description="写入一个完整文本文件。用于创建新文件或整体覆盖已有文件。路径必须位于项目工作区内。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要写入的文件路径，相对于项目根目录。示例：docs/requirements.md",
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入文件的完整文本内容。示例：# Requirements",
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": "目标文件已存在时是否允许整体覆盖。示例：false",
                    },
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
            handler=_write_file,
        ),
        ToolDefinition(
            name="edit_file",
            description="修改文件中的指定文本片段。用于替换、插入或删除已存在的内容。路径必须位于项目工作区内。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要修改的文件路径，相对于项目根目录。示例：src/embedagent/query_engine.py",
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
