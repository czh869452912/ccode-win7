from __future__ import annotations

from typing import Any, Dict, List

from embedagent.tools._base import ToolDefinition
from embedagent.workspace_recipes import RecipeResolutionError
from embedagent_core.session import Observation


def build_tools(ctx) -> List[ToolDefinition]:
    def _list_recipes(arguments: Dict[str, Any]) -> Observation:
        del arguments
        payload = ctx.list_workspace_recipes()
        items = list(payload.get("items") or [])
        preview = []
        for item in items[:10]:
            if not isinstance(item, dict):
                continue
            preview.append(
                "%s[%s]"
                % (
                    str(item.get("id") or ""),
                    str(item.get("recipe_action") or item.get("tool_name") or ""),
                )
            )
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
        try:
            recipe = ctx.resolve_workspace_recipe(
                recipe_id,
                target=str(arguments.get("target") or ""),
                profile=str(arguments.get("profile") or ""),
            )
        except RecipeResolutionError as exc:
            return Observation(
                tool_name="run_recipe",
                success=False,
                error=str(exc),
                data=dict(exc.payload),
            )
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
            recipe_action = str(recipe.get("recipe_action") or "")
            combined = str(data.get("stdout") or "") + "\n" + str(data.get("stderr") or "")
            data["recipe_id"] = recipe_id
            data["recipe_label"] = str(recipe.get("label") or recipe_id)
            data["recipe_source"] = str(recipe.get("source") or "")
            data["recipe_action"] = recipe_action
            data["family"] = str(recipe.get("family") or "")
            data["stage"] = str(recipe.get("stage") or "")
            data["target"] = str(recipe.get("target") or "")
            data["profile"] = str(recipe.get("profile") or "")
            if recipe_action == "test":
                data["test_summary"] = ctx.parse_test_summary(combined)
            if recipe_action == "coverage":
                data["coverage_summary"] = ctx.parse_coverage_summary(combined)
            observation.data = data
        return observation

    def _report_quality_v2(arguments: Dict[str, Any]) -> Observation:
        error_count = int(arguments.get("error_count") or 0)
        warning_count = int(arguments.get("warning_count") or 0)
        test_failures = int(arguments.get("test_failures") or 0)
        passed = error_count == 0 and test_failures == 0
        return Observation(
            tool_name="report_quality_v2",
            success=True,
            error=None,
            data={
                "passed": passed,
                "error_count": error_count,
                "warning_count": warning_count,
                "test_failures": test_failures,
            },
        )

    return [
        ToolDefinition(
            name="list_recipes",
            description="列出当前工作区可运行的 recipe。用于 build/verify 前先选定正确入口。",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
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
                    "recipe_id": {
                        "type": "string",
                        "description": "recipe 标识。示例：detected:build",
                    },
                },
                "required": ["recipe_id"],
                "additionalProperties": False,
            },
            handler=_run_recipe,
        ),
        ToolDefinition(
            name="report_quality_v2",
            description="汇总最小质量门结论。用于把 verify 阶段的错误数、警告数和测试失败数归并成结构化结果。",
            parameters={
                "type": "object",
                "properties": {
                    "error_count": {"type": "integer", "description": "错误数。示例：0"},
                    "warning_count": {"type": "integer", "description": "警告数。示例：1"},
                    "test_failures": {"type": "integer", "description": "测试失败数。示例：0"},
                },
                "required": ["error_count", "warning_count", "test_failures"],
                "additionalProperties": False,
            },
            handler=_report_quality_v2,
            read_only=True,
            concurrency_safe=True,
        ),
    ]
