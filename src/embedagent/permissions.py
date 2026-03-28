from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from embedagent.session import Action


WRITE_TOOLS = {"edit_file"}
COMMAND_TOOLS = {
    "run_command",
    "compile_project",
    "run_tests",
    "run_clang_tidy",
    "run_clang_analyzer",
    "collect_coverage",
}
SAFE_TOOLS = {
    "read_file",
    "list_files",
    "search_text",
    "git_status",
    "git_diff",
    "git_log",
    "report_quality",
    "switch_mode",
}


@dataclass
class PermissionRequest:
    tool_name: str
    category: str
    reason: str
    details: Dict[str, Any]


class PermissionPolicy(object):
    def __init__(
        self,
        auto_approve_all: bool = False,
        auto_approve_writes: bool = False,
        auto_approve_commands: bool = False,
    ) -> None:
        self.auto_approve_all = auto_approve_all
        self.auto_approve_writes = auto_approve_writes
        self.auto_approve_commands = auto_approve_commands

    def build_request(self, action: Action) -> Optional[PermissionRequest]:
        if self.auto_approve_all or action.name in SAFE_TOOLS:
            return None
        if action.name in WRITE_TOOLS:
            if self.auto_approve_writes:
                return None
            path = str(action.arguments.get("path") or "")
            return PermissionRequest(
                tool_name=action.name,
                category="write",
                reason="该操作会修改工作区文件。",
                details={"path": path},
            )
        if action.name in COMMAND_TOOLS:
            if self.auto_approve_commands:
                return None
            command = str(action.arguments.get("command") or "")
            cwd = str(action.arguments.get("cwd") or ".")
            return PermissionRequest(
                tool_name=action.name,
                category="command",
                reason="该操作会执行命令或工具链程序。",
                details={"command": command, "cwd": cwd},
            )
        return None
