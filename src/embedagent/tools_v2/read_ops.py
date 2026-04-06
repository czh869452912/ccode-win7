from __future__ import annotations

from typing import Any, Dict, List

from embedagent.session import Observation
from embedagent.tools._base import ToolDefinition


def build_tools(ctx) -> List[ToolDefinition]:
    def _read_file(arguments: Dict[str, Any]) -> Observation:
        path = ctx.resolve_path(str(arguments.get("path") or ""))
        start_line = max(1, int(arguments.get("start_line") or 1))
        max_lines = max(1, int(arguments.get("max_lines") or 200))
        content, _, encoding = ctx.read_text(path)
        lines = content.split("\n")
        selected = lines[start_line - 1 : start_line - 1 + max_lines]
        return Observation(
            tool_name="read_file",
            success=True,
            error=None,
            data={
                "path": ctx.relative_path(path),
                "preview": "\n".join(selected),
                "encoding": encoding,
                "returned_count": len(selected),
                "total_count": len(lines),
                "has_more": start_line - 1 + len(selected) < len(lines),
                "next_offset": start_line - 1 + len(selected),
                "result_ref": "",
            },
        )

    return [
        ToolDefinition(
            name="read_file",
            description="读取文件片段。用于定点查看文件而不是一次性回灌大文件。支持起始行和最大行数。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径。示例：src/demo.c"},
                    "start_line": {"type": "integer", "description": "起始行号。示例：1"},
                    "max_lines": {"type": "integer", "description": "读取行数上限。示例：200"},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=_read_file,
            read_only=True,
            concurrency_safe=True,
        )
    ]
