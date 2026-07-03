from __future__ import annotations

from typing import Any, Dict, List

from embedagent.interaction import ask_user_schema
from embedagent_core.session import Observation
from embedagent.tools._base import ToolDefinition


def build_interaction_tools(ctx) -> List[ToolDefinition]:
    del ctx

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
            name="ask_user",
            description=str(ask_schema.get("function", {}).get("description") or ""),
            parameters=dict(ask_schema.get("function", {}).get("parameters") or {}),
            handler=_ask_user,
        ),
    ]


def build_workflow_tools(ctx) -> List[ToolDefinition]:
    del ctx

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

    def _record_failing_evidence(arguments: Dict[str, Any]) -> Observation:
        summary = str(arguments.get("summary") or "").strip()
        return Observation(
            tool_name="record_failing_evidence",
            success=True,
            error=None,
            data={
                "summary": summary,
                "failing_evidence_ready": True,
                "result_ref": "",
            },
        )

    return [
        ToolDefinition(
            name="task_status",
            description="读取当前任务状态摘要。用于让模型看到 harness 维护的任务图压缩视图。",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            handler=_task_status,
            read_only=True,
            concurrency_safe=True,
        ),
        ToolDefinition(
            name="record_failing_evidence",
            description="记录当前已复现的失败证据。用于把 debug 过程中的失败现象转换成结构化 artifact。",
            parameters={
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "失败现象摘要。示例：reproduced failure in src/demo.c",
                    }
                },
                "required": ["summary"],
                "additionalProperties": False,
            },
            handler=_record_failing_evidence,
            read_only=True,
            concurrency_safe=True,
        ),
    ]


def build_tools(ctx) -> List[ToolDefinition]:
    definitions = []
    definitions.extend(build_workflow_tools(ctx))
    definitions.extend(build_interaction_tools(ctx))
    return definitions
