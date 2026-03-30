from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

from embedagent import todos as todo_store
from embedagent.session import Observation
from embedagent.tools._base import ToolContext, ToolDefinition, ToolError


def build_tools(ctx: ToolContext) -> List[ToolDefinition]:

    def _session_id(arguments: Dict[str, Any]) -> str:
        return str(arguments.get("session_id") or "").strip()

    def _load_todos(session_id: str) -> List[Dict[str, Any]]:
        return todo_store.load_todos(ctx.workspace, session_id=session_id)

    def _save_todos(todos: List[Dict[str, Any]], session_id: str) -> None:
        todo_store.save_todos(ctx.workspace, todos, session_id=session_id)

    def _manage_todos(arguments: Dict[str, Any]) -> Observation:
        action = str(arguments.get("action") or "").strip()
        content = str(arguments.get("content") or "").strip()
        item_id = arguments.get("item_id")
        item_id_int = int(item_id) if item_id is not None else None
        session_id = _session_id(arguments)

        if action not in ("list", "add", "complete", "remove"):
            raise ToolError("action 必须是 list、add、complete 或 remove。")

        todos = _load_todos(session_id)

        if action == "list":
            return Observation(
                tool_name="manage_todos",
                success=True,
                error=None,
                data={
                    "action": "list",
                    "count": len(todos),
                    "todos": todos,
                    "session_id": session_id,
                    "path": todo_store.relative_todos_path(session_id),
                },
            )

        if action == "add":
            if not content:
                raise ToolError("add 操作需要提供 content 参数。")
            next_id = (max(t["id"] for t in todos) + 1) if todos else 1
            todos.append({
                "id": next_id,
                "content": content,
                "done": False,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            })
            _save_todos(todos, session_id)
            return Observation(
                tool_name="manage_todos",
                success=True,
                error=None,
                data={
                    "action": "add",
                    "id": next_id,
                    "content": content,
                    "session_id": session_id,
                    "path": todo_store.relative_todos_path(session_id),
                },
            )

        if action == "complete":
            if item_id_int is None:
                raise ToolError("complete 操作需要提供 item_id 参数。")
            for todo in todos:
                if todo["id"] == item_id_int:
                    todo["done"] = True
                    _save_todos(todos, session_id)
                    return Observation(
                        tool_name="manage_todos",
                        success=True,
                        error=None,
                        data={
                            "action": "complete",
                            "id": item_id_int,
                            "session_id": session_id,
                            "path": todo_store.relative_todos_path(session_id),
                        },
                    )
            raise ToolError("未找到 id=%s 的待办项。" % item_id_int)

        if action == "remove":
            if item_id_int is None:
                raise ToolError("remove 操作需要提供 item_id 参数。")
            original_len = len(todos)
            todos = [t for t in todos if t["id"] != item_id_int]
            if len(todos) == original_len:
                raise ToolError("未找到 id=%s 的待办项。" % item_id_int)
            # Renumber remaining items sequentially
            for index, todo in enumerate(todos, start=1):
                todo["id"] = index
            _save_todos(todos, session_id)
            return Observation(
                tool_name="manage_todos",
                success=True,
                error=None,
                data={
                    "action": "remove",
                    "removed_id": item_id_int,
                    "remaining": len(todos),
                    "session_id": session_id,
                    "path": todo_store.relative_todos_path(session_id),
                },
            )

        raise ToolError("未知操作：%s" % action)

    return [
        ToolDefinition(
            name="manage_todos",
            description="管理任务清单。增删改查待办项，跟踪多步任务进度。每次会话开始时可用 list 查看未完成项。",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "add", "complete", "remove"],
                        "description": "操作类型：list 列出所有、add 新增、complete 标记完成、remove 删除。示例：add",
                    },
                    "content": {
                        "type": "string",
                        "description": "待办项内容，仅 add 操作需要。示例：实现 login 接口",
                    },
                    "item_id": {
                        "type": "integer",
                        "description": "待办项编号，complete 和 remove 操作需要。示例：2",
                    },
                    "session_id": {
                        "type": "string",
                        "description": "会话 ID。由运行时自动注入；仅在前端显式读取某个会话待办时需要。示例：abc123",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
            handler=_manage_todos,
        ),
    ]
