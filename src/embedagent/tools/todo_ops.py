from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

from embedagent.session import Observation
from embedagent.tools._base import ToolContext, ToolDefinition, ToolError

_TODOS_FILE = os.path.join(".embedagent", "todos.json")


def build_tools(ctx: ToolContext) -> List[ToolDefinition]:

    def _todos_path() -> str:
        return os.path.join(ctx.workspace, ".embedagent", "todos.json")

    def _load_todos() -> List[Dict[str, Any]]:
        path = _todos_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, list) else []
        except (ValueError, IOError):
            return []

    def _save_todos(todos: List[Dict[str, Any]]) -> None:
        path = _todos_path()
        parent = os.path.dirname(path)
        if not os.path.exists(parent):
            os.makedirs(parent)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(todos, fh, ensure_ascii=False, indent=2)

    def _manage_todos(arguments: Dict[str, Any]) -> Observation:
        action = str(arguments.get("action") or "").strip()
        content = str(arguments.get("content") or "").strip()
        item_id = arguments.get("item_id")
        item_id_int = int(item_id) if item_id is not None else None

        if action not in ("list", "add", "complete", "remove"):
            raise ToolError("action 必须是 list、add、complete 或 remove。")

        todos = _load_todos()

        if action == "list":
            return Observation(
                tool_name="manage_todos",
                success=True,
                error=None,
                data={"action": "list", "count": len(todos), "todos": todos},
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
            _save_todos(todos)
            return Observation(
                tool_name="manage_todos",
                success=True,
                error=None,
                data={"action": "add", "id": next_id, "content": content},
            )

        if action == "complete":
            if item_id_int is None:
                raise ToolError("complete 操作需要提供 item_id 参数。")
            for todo in todos:
                if todo["id"] == item_id_int:
                    todo["done"] = True
                    _save_todos(todos)
                    return Observation(
                        tool_name="manage_todos",
                        success=True,
                        error=None,
                        data={"action": "complete", "id": item_id_int},
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
            _save_todos(todos)
            return Observation(
                tool_name="manage_todos",
                success=True,
                error=None,
                data={"action": "remove", "removed_id": item_id_int, "remaining": len(todos)},
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
                },
                "required": ["action"],
                "additionalProperties": False,
            },
            handler=_manage_todos,
        ),
    ]
