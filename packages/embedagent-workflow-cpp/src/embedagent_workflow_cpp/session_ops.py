from __future__ import annotations

from typing import Any, Dict, List

from embedagent_core.session import Observation
from embedagent_core.tool_contracts import ToolDefinition


def build_workflow_tools(ctx: Any) -> List[ToolDefinition]:
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
            description="读取当前 C/C++ workflow 任务状态摘要。",
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
