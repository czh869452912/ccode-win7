from __future__ import annotations

from typing import Any, Dict, List, Optional

from embedagent.session import Observation
from embedagent.tools._base import DEFAULT_BUILD_TIMEOUT_SEC, ToolContext, ToolDefinition


def build_tools(ctx: ToolContext) -> List[ToolDefinition]:

    def _resolve_recipe(arguments: Dict[str, Any], expected_tool_name: str) -> Dict[str, Any]:
        recipe_id = str(arguments.get("recipe_id") or "").strip()
        if not recipe_id:
            return {}
        resolved = ctx.resolve_workspace_recipe(
            recipe_id=recipe_id,
            expected_tool_name=expected_tool_name,
            target=str(arguments.get("target") or ""),
            profile=str(arguments.get("profile") or ""),
        )
        return resolved

    def _compile_project(arguments: Dict[str, Any]) -> Observation:
        recipe = _resolve_recipe(arguments, "compile_project")
        command_text = str(recipe.get("command") or arguments.get("command") or "").strip()
        cwd_argument = str(recipe.get("cwd") or arguments.get("cwd") or ".")
        timeout_sec = int(arguments.get("timeout_sec") or DEFAULT_BUILD_TIMEOUT_SEC)
        observation = ctx.run_shell_tool("compile_project", command_text, cwd_argument, timeout_sec, diagnostic=True)
        if recipe and isinstance(observation.data, dict):
            data = dict(observation.data)
            data["recipe_id"] = recipe.get("id") or recipe.get("recipe_id") or str(arguments.get("recipe_id") or "")
            data["recipe_source"] = recipe.get("source") or ""
            data["recipe_label"] = recipe.get("label") or data["recipe_id"]
            data["target"] = recipe.get("target") or ""
            data["profile"] = recipe.get("profile") or ""
            observation.data = data
        return observation

    def _run_tests(arguments: Dict[str, Any]) -> Observation:
        recipe = _resolve_recipe(arguments, "run_tests")
        command_text = str(recipe.get("command") or arguments.get("command") or "").strip()
        cwd_argument = str(recipe.get("cwd") or arguments.get("cwd") or ".")
        timeout_sec = int(arguments.get("timeout_sec") or DEFAULT_BUILD_TIMEOUT_SEC)
        observation = ctx.run_shell_tool("run_tests", command_text, cwd_argument, timeout_sec, diagnostic=True)
        combined = (observation.data.get("stdout") or "") + "\n" + (observation.data.get("stderr") or "")
        observation.data.update({"test_summary": ctx.parse_test_summary(combined)})
        if recipe and isinstance(observation.data, dict):
            observation.data["recipe_id"] = recipe.get("id") or recipe.get("recipe_id") or str(arguments.get("recipe_id") or "")
            observation.data["recipe_source"] = recipe.get("source") or ""
            observation.data["recipe_label"] = recipe.get("label") or observation.data["recipe_id"]
            observation.data["target"] = recipe.get("target") or ""
            observation.data["profile"] = recipe.get("profile") or ""
        return observation

    def _run_clang_tidy(arguments: Dict[str, Any]) -> Observation:
        recipe = _resolve_recipe(arguments, "run_clang_tidy")
        command_text = str(recipe.get("command") or arguments.get("command") or "").strip()
        cwd_argument = str(recipe.get("cwd") or arguments.get("cwd") or ".")
        timeout_sec = int(arguments.get("timeout_sec") or DEFAULT_BUILD_TIMEOUT_SEC)
        observation = ctx.run_shell_tool("run_clang_tidy", command_text, cwd_argument, timeout_sec, diagnostic=True)
        if recipe and isinstance(observation.data, dict):
            observation.data["recipe_id"] = recipe.get("id") or recipe.get("recipe_id") or str(arguments.get("recipe_id") or "")
            observation.data["recipe_source"] = recipe.get("source") or ""
            observation.data["recipe_label"] = recipe.get("label") or observation.data["recipe_id"]
            observation.data["target"] = recipe.get("target") or ""
            observation.data["profile"] = recipe.get("profile") or ""
        return observation

    def _run_clang_analyzer(arguments: Dict[str, Any]) -> Observation:
        recipe = _resolve_recipe(arguments, "run_clang_analyzer")
        command_text = str(recipe.get("command") or arguments.get("command") or "").strip()
        cwd_argument = str(recipe.get("cwd") or arguments.get("cwd") or ".")
        timeout_sec = int(arguments.get("timeout_sec") or DEFAULT_BUILD_TIMEOUT_SEC)
        observation = ctx.run_shell_tool("run_clang_analyzer", command_text, cwd_argument, timeout_sec, diagnostic=True)
        if recipe and isinstance(observation.data, dict):
            observation.data["recipe_id"] = recipe.get("id") or recipe.get("recipe_id") or str(arguments.get("recipe_id") or "")
            observation.data["recipe_source"] = recipe.get("source") or ""
            observation.data["recipe_label"] = recipe.get("label") or observation.data["recipe_id"]
            observation.data["target"] = recipe.get("target") or ""
            observation.data["profile"] = recipe.get("profile") or ""
        return observation

    def _collect_coverage(arguments: Dict[str, Any]) -> Observation:
        recipe = _resolve_recipe(arguments, "collect_coverage")
        command_text = str(recipe.get("command") or arguments.get("command") or "").strip()
        cwd_argument = str(recipe.get("cwd") or arguments.get("cwd") or ".")
        timeout_sec = int(arguments.get("timeout_sec") or DEFAULT_BUILD_TIMEOUT_SEC)
        observation = ctx.run_shell_tool("collect_coverage", command_text, cwd_argument, timeout_sec)
        combined = (observation.data.get("stdout") or "") + "\n" + (observation.data.get("stderr") or "")
        observation.data.update({"coverage_summary": ctx.parse_coverage_summary(combined)})
        if recipe and isinstance(observation.data, dict):
            observation.data["recipe_id"] = recipe.get("id") or recipe.get("recipe_id") or str(arguments.get("recipe_id") or "")
            observation.data["recipe_source"] = recipe.get("source") or ""
            observation.data["recipe_label"] = recipe.get("label") or observation.data["recipe_id"]
            observation.data["target"] = recipe.get("target") or ""
            observation.data["profile"] = recipe.get("profile") or ""
        return observation

    def _report_quality(arguments: Dict[str, Any]) -> Observation:
        error_count = int(arguments.get("error_count") or 0)
        test_failures = int(arguments.get("test_failures") or 0)
        warning_count = int(arguments.get("warning_count") or 0)
        line_coverage = arguments.get("line_coverage")
        min_line_coverage = arguments.get("min_line_coverage")
        line_coverage_value = float(line_coverage) if line_coverage is not None else None  # type: Optional[float]
        min_line_coverage_value = float(min_line_coverage) if min_line_coverage is not None else None  # type: Optional[float]
        reasons = []
        if error_count > 0:
            reasons.append("存在 %s 个错误。" % error_count)
        if test_failures > 0:
            reasons.append("存在 %s 个失败测试。" % test_failures)
        if (
            line_coverage_value is not None
            and min_line_coverage_value is not None
            and line_coverage_value < min_line_coverage_value
        ):
            reasons.append("行覆盖率 %.2f%% 低于阈值 %.2f%%。" % (line_coverage_value, min_line_coverage_value))
        passed = not reasons
        data = {
            "passed": passed,
            "error_count": error_count,
            "warning_count": warning_count,
            "test_failures": test_failures,
            "line_coverage": line_coverage_value,
            "min_line_coverage": min_line_coverage_value,
            "reasons": reasons,
        }
        return Observation(
            tool_name="report_quality",
            success=passed,
            error=None if passed else "质量门未通过。",
            data=data,
        )

    return [
        ToolDefinition(
            name="compile_project",
            description="执行项目编译命令。用于构建目标程序并解析编译诊断。命令应输出可解析的编译器信息。",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的编译命令文本。示例：clang -Wall -Wextra src/main.c -o build/main.exe",
                    },
                    "recipe_id": {
                        "type": "string",
                        "description": "可选的工作区 recipe 标识。示例：cmake.build.default",
                    },
                    "target": {
                        "type": "string",
                        "description": "可选的构建目标；当前主要用于支持 CMake build recipe。示例：app",
                    },
                    "profile": {
                        "type": "string",
                        "description": "可选的构建 profile；当前主要用于支持 CMake build 目录。示例：debug",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "编译执行目录，相对于项目根目录。示例：.",
                    },
                    "timeout_sec": {
                        "type": "integer",
                        "description": "编译超时时间，单位为秒。示例：120",
                    },
                },
                "required": [],
                "anyOf": [
                    {"required": ["command"]},
                    {"required": ["recipe_id"]},
                ],
                "additionalProperties": False,
            },
            handler=_compile_project,
        ),
        ToolDefinition(
            name="run_tests",
            description="执行测试命令并汇总结果。用于运行单元测试、集成测试或测试驱动脚本。命令应输出可统计的测试结果。",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的测试命令文本。示例：ctest --output-on-failure",
                    },
                    "recipe_id": {
                        "type": "string",
                        "description": "可选的工作区 recipe 标识。示例：cmake.test.default",
                    },
                    "target": {
                        "type": "string",
                        "description": "可选的测试目标或筛选；当前保留给后续 recipe 扩展。示例：unit",
                    },
                    "profile": {
                        "type": "string",
                        "description": "可选的测试 profile；当前主要用于支持 CMake build 目录。示例：debug",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "测试执行目录，相对于项目根目录。示例：build",
                    },
                    "timeout_sec": {
                        "type": "integer",
                        "description": "测试超时时间，单位为秒。示例：120",
                    },
                },
                "required": [],
                "anyOf": [
                    {"required": ["command"]},
                    {"required": ["recipe_id"]},
                ],
                "additionalProperties": False,
            },
            handler=_run_tests,
        ),
        ToolDefinition(
            name="run_clang_tidy",
            description="执行 clang-tidy 检查命令。用于收集静态检查警告和错误。命令应输出 clang 风格诊断。",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的 clang-tidy 命令文本。示例：clang-tidy src/main.c -- -Iinclude",
                    },
                    "recipe_id": {
                        "type": "string",
                        "description": "可选的工作区 recipe 标识。示例：history.run_clang_tidy.1",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "检查执行目录，相对于项目根目录。示例：.",
                    },
                    "timeout_sec": {
                        "type": "integer",
                        "description": "检查超时时间，单位为秒。示例：120",
                    },
                },
                "required": [],
                "anyOf": [
                    {"required": ["command"]},
                    {"required": ["recipe_id"]},
                ],
                "additionalProperties": False,
            },
            handler=_run_clang_tidy,
        ),
        ToolDefinition(
            name="run_clang_analyzer",
            description="执行 clang 静态分析命令。用于收集分析器发现的问题和定位信息。命令应输出 clang 风格诊断。",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的静态分析命令文本。示例：clang --analyze src/main.c -Iinclude",
                    },
                    "recipe_id": {
                        "type": "string",
                        "description": "可选的工作区 recipe 标识。示例：history.run_clang_analyzer.1",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "分析执行目录，相对于项目根目录。示例：.",
                    },
                    "timeout_sec": {
                        "type": "integer",
                        "description": "分析超时时间，单位为秒。示例：120",
                    },
                },
                "required": [],
                "anyOf": [
                    {"required": ["command"]},
                    {"required": ["recipe_id"]},
                ],
                "additionalProperties": False,
            },
            handler=_run_clang_analyzer,
        ),
        ToolDefinition(
            name="collect_coverage",
            description="执行覆盖率收集命令。用于汇总覆盖率报告并提取核心百分比。命令应输出可识别的覆盖率文本。",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的覆盖率命令文本。示例：llvm-cov report build/app.exe -instr-profile=default.profdata",
                    },
                    "recipe_id": {
                        "type": "string",
                        "description": "可选的工作区 recipe 标识。示例：history.collect_coverage.1",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "覆盖率执行目录，相对于项目根目录。示例：build",
                    },
                    "timeout_sec": {
                        "type": "integer",
                        "description": "覆盖率命令超时时间，单位为秒。示例：120",
                    },
                },
                "required": [],
                "anyOf": [
                    {"required": ["command"]},
                    {"required": ["recipe_id"]},
                ],
                "additionalProperties": False,
            },
            handler=_collect_coverage,
        ),
        ToolDefinition(
            name="report_quality",
            description="评估当前质量门结果。用于根据错误数、失败测试和覆盖率判断是否通过。参数应来自前置工具 Observation。",
            parameters={
                "type": "object",
                "properties": {
                    "error_count": {
                        "type": "integer",
                        "description": "当前累计错误数。示例：0",
                    },
                    "test_failures": {
                        "type": "integer",
                        "description": "当前失败测试数。示例：0",
                    },
                    "warning_count": {
                        "type": "integer",
                        "description": "当前累计警告数，未传时按 0 处理。示例：3",
                    },
                    "line_coverage": {
                        "type": "number",
                        "description": "当前语句或行覆盖率百分比。示例：85.5",
                    },
                    "min_line_coverage": {
                        "type": "number",
                        "description": "最低可接受的行覆盖率百分比。示例：80.0",
                    },
                },
                "required": ["error_count", "test_failures"],
                "additionalProperties": False,
            },
            handler=_report_quality,
        ),
    ]
