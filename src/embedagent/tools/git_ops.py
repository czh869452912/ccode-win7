from __future__ import annotations

from typing import Any, Dict, List

from embedagent.session import Observation
from embedagent.tools._base import ToolContext, ToolDefinition, ToolError


def build_tools(ctx: ToolContext) -> List[ToolDefinition]:

    def _git_status(arguments: Dict[str, Any]) -> Observation:
        path_argument = str(arguments["path"])
        relative_arg = ctx.git_relative_arg(path_argument)
        command = ["git", "-C", ctx.workspace, "status", "--short", "--branch"]
        if relative_arg:
            command.extend(["--", relative_arg])
        result = ctx.run_git_command(command)
        observation = ctx.build_command_observation("git_status", " ".join(command), ctx.workspace, result)
        if not observation.success:
            return observation
        lines = [line for line in result["stdout"].splitlines() if line]
        branch = ""
        entries = []
        for line in lines:
            if line.startswith("## "):
                branch = line[3:].strip()
                continue
            status_code = line[:2]
            file_path = line[3:].strip() if len(line) > 3 else ""
            entries.append({"status": status_code, "path": file_path})
        observation.data.update({"path": path_argument, "branch": branch, "entries": entries})
        return observation

    def _git_diff(arguments: Dict[str, Any]) -> Observation:
        path_argument = str(arguments["path"])
        scope = str(arguments.get("scope") or "working")
        if scope not in ("working", "staged"):
            raise ToolError("scope 只能是 working 或 staged。")
        relative_arg = ctx.git_relative_arg(path_argument)
        command = ["git", "-C", ctx.workspace, "diff"]
        if scope == "staged":
            command.append("--cached")
        if relative_arg:
            command.extend(["--", relative_arg])
        result = ctx.run_git_command(command)
        observation = ctx.build_command_observation("git_diff", " ".join(command), ctx.workspace, result)
        if not observation.success:
            return observation
        diff_text = result["stdout"]
        observation.data.update({
            "path": path_argument,
            "scope": scope,
            "file_count": diff_text.count("diff --git "),
            "line_count": diff_text.count("\n") + (1 if diff_text else 0),
            "diff": diff_text,
        })
        return observation

    def _git_log(arguments: Dict[str, Any]) -> Observation:
        path_argument = str(arguments["path"])
        limit = int(arguments.get("limit") or 10)
        if limit <= 0:
            raise ToolError("limit 必须大于 0。")
        relative_arg = ctx.git_relative_arg(path_argument)
        command = [
            "git", "-C", ctx.workspace, "log",
            "--date=iso-strict",
            "--pretty=format:%H%x1f%an%x1f%ad%x1f%s%x1e",
            "-n", str(limit),
        ]
        if relative_arg:
            command.extend(["--", relative_arg])
        result = ctx.run_git_command(command)
        observation = ctx.build_command_observation("git_log", " ".join(command), ctx.workspace, result)
        if not observation.success:
            return observation
        entries = []
        for record in result["stdout"].split("\x1e"):
            record = record.strip()
            if not record:
                continue
            parts = record.split("\x1f")
            if len(parts) != 4:
                continue
            entries.append({"commit": parts[0], "author": parts[1], "date": parts[2], "subject": parts[3]})
        observation.data.update({"path": path_argument, "limit": limit, "entries": entries})
        return observation

    return [
        ToolDefinition(
            name="git_status",
            description="查看当前 Git 工作区状态。用于确认分支、未提交修改和未跟踪文件。路径必须位于当前仓库内。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要查看的仓库路径或子路径，相对于项目根目录。示例：.",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=_git_status,
        ),
        ToolDefinition(
            name="git_diff",
            description="查看 Git 差异内容。用于检查未提交修改或已暂存修改的具体文本差异。路径必须位于当前仓库内。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要查看的仓库路径或子路径，相对于项目根目录。示例：.",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["working", "staged"],
                        "description": "差异范围，working 表示工作区，staged 表示已暂存。示例：working",
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=_git_diff,
        ),
        ToolDefinition(
            name="git_log",
            description="查看最近的 Git 提交历史。用于了解最近改动、作者和提交主题。路径必须位于当前仓库内。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要查看的仓库路径或子路径，相对于项目根目录。示例：.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "要返回的提交条数，默认 10。示例：5",
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=_git_log,
        ),
    ]
