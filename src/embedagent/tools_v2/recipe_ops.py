from __future__ import annotations

from typing import Any, Dict, List

from embedagent.session import Observation
from embedagent.tools._base import ToolDefinition


def build_tools(ctx) -> List[ToolDefinition]:
    def _list_recipes(arguments: Dict[str, Any]) -> Observation:
        del arguments
        payload = ctx.list_workspace_recipes()
        items = list(payload.get("items") or [])
        preview = []
        for item in items[:10]:
            if not isinstance(item, dict):
                continue
            preview.append("%s[%s]" % (str(item.get("id") or ""), str(item.get("tool_name") or "")))
        return Observation(
            tool_name="list_recipes",
            success=True,
            error=None,
            data={
                "preview": preview,
                "returned_count": len(preview),
                "total_count": len(items),
                "has_more": len(preview) < len(items),
                "next_offset": len(preview),
                "result_ref": "",
                "items": items,
            },
        )

    def _run_recipe(arguments: Dict[str, Any]) -> Observation:
        recipe_id = str(arguments.get("recipe_id") or "").strip()
        recipe = ctx.resolve_workspace_recipe(recipe_id)
        command_text = str(recipe.get("command") or "")
        cwd_argument = str(recipe.get("cwd") or ".")
        timeout_sec = int(recipe.get("timeout_sec") or 120)
        observation = ctx.run_shell_tool(
            tool_name="run_recipe",
            command_text=command_text,
            cwd_argument=cwd_argument,
            timeout_sec=timeout_sec,
            diagnostic=True,
        )
        if isinstance(observation.data, dict):
            data = dict(observation.data)
            data["recipe_id"] = recipe_id
            observation.data = data
        return observation

    return [
        ToolDefinition(
            name="list_recipes",
            description="列出当前工作区可运行的 recipe。用于 build/verify 前先选定正确入口。",
            parameters={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            handler=_list_recipes,
            read_only=True,
            concurrency_safe=True,
        ),
        ToolDefinition(
            name="run_recipe",
            description="运行工作区 recipe。用于统一执行 build、test 或 verify 入口。依赖已配置好的 recipe_id。",
            parameters={
                "type": "object",
                "properties": {
                    "recipe_id": {"type": "string", "description": "recipe 标识。示例：detected:build"},
                },
                "required": ["recipe_id"],
                "additionalProperties": False,
            },
            handler=_run_recipe,
        ),
    ]
