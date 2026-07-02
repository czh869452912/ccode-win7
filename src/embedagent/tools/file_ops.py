from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from embedagent.services.shadow_git import ShadowGitSnapshot
from embedagent.session import Observation
from embedagent.strategies.diff_engine import DiffBlock, MultiSearchReplaceDiffEngine
from embedagent.tools._base import (
    MAX_READ_CHARS,
    ToolContext,
    ToolDefinition,
    ToolError,
    diagnostic_tool_error,
)

logger = logging.getLogger(__name__)


def _read_file_tool_error(error: ToolError) -> ToolError:
    text = str(error)
    if "路径不存在" in text:
        return diagnostic_tool_error(
            text,
            "path_not_found",
            "Use list_dir or glob_files to find the correct file path.",
        )
    if "路径超出当前工作区" in text:
        return diagnostic_tool_error(
            text,
            "path_outside_workspace",
            "Read only files inside the current workspace.",
        )
    if "只能读取文件" in text:
        return diagnostic_tool_error(
            text,
            "not_file",
            "Use list_dir for directories or choose a file path.",
        )
    if "文件看起来不是文本文件" in text:
        return diagnostic_tool_error(
            text,
            "binary_file",
            "Use file discovery tools to inspect names and read only text files.",
        )
    if "文件编码无法识别" in text:
        return diagnostic_tool_error(
            text,
            "unknown_encoding",
            "Try another text file or inspect the file encoding outside read_file.",
        )
    return error


def build_tools(ctx: ToolContext) -> List[ToolDefinition]:

    def _read_file(arguments: Dict[str, Any]) -> Observation:
        try:
            path = ctx.resolve_path(str(arguments["path"]))
            if not os.path.isfile(path):
                raise ToolError("只能读取文件，不能读取目录。")
            content, _, encoding = ctx.read_text(path)
        except ToolError as exc:
            raise _read_file_tool_error(exc)
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

        # Create pre-edit snapshot
        try:
            snapshot = ShadowGitSnapshot(ctx.workspace)
            snapshot.create_snapshot(reason="pre_edit:edit_file")
        except (ToolError, OSError, ValueError) as exc:
            logger.warning("Pre-edit snapshot failed: %s", exc)

        content, newline_style, encoding = ctx.read_text(path)
        engine = MultiSearchReplaceDiffEngine()

        # Build blocks from arguments
        blocks = []
        if "blocks" in arguments and arguments["blocks"]:
            for block_data in arguments["blocks"]:
                blocks.append(
                    DiffBlock(
                        old_text=str(block_data["old_text"]),
                        new_text=str(block_data["new_text"]),
                        expected_start_line=block_data.get("expected_start_line"),
                        fuzzy=block_data.get("fuzzy", True),
                    )
                )
        else:
            old_text = str(arguments["old_text"])
            new_text = str(arguments["new_text"])
            if not old_text:
                raise ToolError("old_text 不能为空。")
            blocks.append(DiffBlock(old_text=old_text, new_text=new_text))

        updated_content, results = engine.apply_diff(content, blocks)

        # Check results
        failed = [r for r in results if r["status"] != "applied"]
        if failed:
            error_msg = "; ".join("Block %d: %s" % (r["block_index"], r["message"]) for r in failed)
            raise ToolError("编辑失败：%s" % error_msg)

        ctx.write_text(path, updated_content, newline_style, encoding)

        applied_count = len([r for r in results if r["status"] == "applied"])
        return Observation(
            tool_name="edit_file",
            success=True,
            error=None,
            data={
                "path": ctx.relative_path(path),
                "encoding": encoding,
                "replaced": True,
                "applied_blocks": applied_count,
                "line_count": updated_content.count("\n") + (1 if updated_content else 0),
            },
        )

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
            description="修改文件中的指定文本片段。支持单次替换或多块替换。路径必须位于项目工作区内。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要修改的文件路径，相对于项目根目录。示例：src/embedagent_core/query_engine.py",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "要被替换的原始文本，必须与文件内容完全一致。示例：print('old')",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "替换后的新文本，传入空字符串表示删除。示例：print('new')",
                    },
                    "blocks": {
                        "type": "array",
                        "description": "多块替换模式，每个块包含 old_text 和 new_text。与 old_text/new_text 互斥。",
                        "items": {
                            "type": "object",
                            "properties": {
                                "old_text": {"type": "string"},
                                "new_text": {"type": "string"},
                                "expected_start_line": {"type": "integer"},
                                "fuzzy": {"type": "boolean"},
                            },
                            "required": ["old_text", "new_text"],
                        },
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=_edit_file,
        ),
    ]
