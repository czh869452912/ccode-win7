from __future__ import annotations

from typing import Any, Dict, List

from embedagent.interaction import ask_user_schema
from embedagent.session import Observation
from embedagent.tools._base import ToolDefinition


def build_tools(ctx) -> List[ToolDefinition]:
    def _task_status(arguments: Dict[str, Any]) -> Observation:
        del arguments
        return Observation(
            tool_name="task_status",
            success=True,
            error=None,
            data={
                "preview": [],
                "returned_count": 0,
                "total_count": 0,
                "has_more": False,
                "next_offset": 0,
                "result_ref": "",
            },
        )

    def _ask_user(arguments: Dict[str, Any]) -> Observation:
        del arguments
        return Observation(
            tool_name="ask_user",
            success=False,
            error="ask_user 由 QueryEngine 交互链路处理，runtime 不直接执行。",
            data={"error_kind": "interaction_only"},
        )

    ask_schema = ask_user_schema()
    return [
        ToolDefinition(
            name="task_status",
            description="读取当前任务状态摘要。用于让模型看到 harness 维护的任务图压缩视图。",
            parameters={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            handler=_task_status,
            read_only=True,
            concurrency_safe=True,
        ),
        ToolDefinition(
            name="ask_user",
            description=str(ask_schema.get("function", {}).get("description") or ""),
            parameters=dict(ask_schema.get("function", {}).get("parameters") or {}),
            handler=_ask_user,
        ),
    ]
