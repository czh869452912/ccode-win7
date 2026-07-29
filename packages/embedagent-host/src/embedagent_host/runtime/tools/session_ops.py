from __future__ import annotations

from typing import Any, Dict, List

from embedagent_core.interaction import ask_user_schema
from embedagent_core.session import Observation
from embedagent_core.tool_contracts import ToolDefinition


def build_interaction_tools(ctx) -> List[ToolDefinition]:
    del ctx

    def _ask_user(arguments: Dict[str, Any]) -> Observation:
        del arguments
        return Observation(
            tool_name="ask_user",
            success=False,
            error="ask_user 由 AgentSession 交互链路处理，runtime 不直接执行。",
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
