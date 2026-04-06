from __future__ import annotations

from typing import Any, Dict, List

from embedagent.session import Observation
from embedagent.tools._base import ToolDefinition, ToolError


def build_tools(ctx) -> List[ToolDefinition]:
    def _edit_file(arguments: Dict[str, Any]) -> Observation:
        path = ctx.resolve_path(str(arguments.get("path") or ""))
        old_text = str(arguments.get("old_text") or "")
        new_text = str(arguments.get("new_text") or "")
        content, newline_style, encoding = ctx.read_text(path)
        if old_text not in content:
            raise ToolError("old_text 未命中目标文件内容。")
        updated = content.replace(old_text, new_text, 1)
        ctx.write_text(path, updated, newline_style, encoding)
        return Observation(
            tool_name="edit_file",
            success=True,
            error=None,
            data={
                "path": ctx.relative_path(path),
                "replaced": True,
                "result_ref": "",
            },
        )

    def _write_file(arguments: Dict[str, Any]) -> Observation:
        path = ctx.resolve_path(str(arguments.get("path") or ""), allow_missing=True)
        content = str(arguments.get("content") or "")
        parent = ctx.resolve_path(".", allow_missing=True)
        del parent
        import os

        container = os.path.dirname(path)
        if container and not os.path.isdir(container):
            os.makedirs(container)
        ctx.write_text(path, content, "\n", "utf-8")
        return Observation(
            tool_name="write_file",
            success=True,
            error=None,
            data={
                "path": ctx.relative_path(path),
                "created": True,
                "result_ref": "",
            },
        )

    return [
        ToolDefinition(
            name="edit_file",
            description="精确替换已存在文件中的文本。用于最小化修改现有内容。编辑前应先读取目标文件。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径。示例：src/demo.c"},
                    "old_text": {"type": "string", "description": "原文本。示例：return 0;"},
                    "new_text": {"type": "string", "description": "新文本。示例：return 1;"},
                },
                "required": ["path", "old_text", "new_text"],
                "additionalProperties": False,
            },
            handler=_edit_file,
        ),
        ToolDefinition(
            name="write_file",
            description="写入完整文件内容。用于新建文件或整体重写。已有文件优先考虑 edit_file。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径。示例：docs/spec.md"},
                    "content": {"type": "string", "description": "完整文件内容。示例：# spec"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
            handler=_write_file,
        ),
    ]
