from __future__ import annotations

import fnmatch
import re
from typing import Dict, List, Tuple


DEFAULT_MODE = "code"

MODE_REGISTRY = {
    "ask": {
        "slug": "ask",
        "system_prompt": "你当前处于 ask 模式，只负责澄清信息缺口与关键决策，不直接修改代码。若任务需要实现或验证，请先切换到更合适的模式。",
        "allowed_tools": ["read_file", "list_files", "search_text"],
        "writable_globs": [],
    },
    "orchestra": {
        "slug": "orchestra",
        "system_prompt": "你当前处于 orchestra 模式，负责拆解任务、选择后续模式并协调步骤，不直接承担大规模实现。若需要具体执行，请先切换到对应模式。",
        "allowed_tools": ["read_file", "list_files", "search_text", "git_status"],
        "writable_globs": [],
    },
    "spec": {
        "slug": "spec",
        "system_prompt": "你当前处于 spec 模式，负责整理需求、边界条件、验收标准和文档，不直接承担命令执行或开放式调试。修改范围应限制在文档文件。",
        "allowed_tools": ["read_file", "list_files", "search_text", "edit_file"],
        "writable_globs": ["docs/**/*.md", "docs/*.md", "README.md"],
    },
    "code": {
        "slug": "code",
        "system_prompt": "你当前处于 code 模式，负责以最小变更实现代码。只在明确需要时修改源码或项目配置，必要时用 run_command 做最小验证。",
        "allowed_tools": ["read_file", "edit_file", "search_text", "run_command"],
        "writable_globs": ["src/**/*.py", "src/*.py", "pyproject.toml"],
    },
    "test": {
        "slug": "test",
        "system_prompt": "你当前处于 test 模式，负责编写或调整测试入口、验证脚本和测试辅助代码。优先让问题可复现，再推进实现。",
        "allowed_tools": ["read_file", "edit_file", "search_text", "run_command"],
        "writable_globs": ["tests/**/*.py", "tests/*.py", "src/**/*.py", "src/*.py"],
    },
    "verify": {
        "slug": "verify",
        "system_prompt": "你当前处于 verify 模式，负责执行检查、查看差异和汇总验证结果，不直接编辑源码。若发现需要改动，请切换到 code 或 debug。",
        "allowed_tools": ["run_command", "git_status", "git_diff", "git_log"],
        "writable_globs": [],
    },
    "debug": {
        "slug": "debug",
        "system_prompt": "你当前处于 debug 模式，负责复现问题、定位根因并做最小修复。优先用读取、搜索和最小命令验证缩小范围。",
        "allowed_tools": ["read_file", "search_text", "edit_file", "run_command"],
        "writable_globs": ["src/**/*.py", "src/*.py", "tests/**/*.py", "tests/*.py"],
    },
    "compact": {
        "slug": "compact",
        "system_prompt": "你当前处于 compact 模式，只负责整理上下文与压缩摘要，不直接改代码或执行高风险动作。必要时切换回其他模式继续工作。",
        "allowed_tools": ["read_file", "list_files", "search_text"],
        "writable_globs": [],
    },
}

_MODE_COMMAND_RE = re.compile(r"^/mode\s+(\w+)(?:\s+(.*))?$", re.DOTALL)


def mode_names() -> List[str]:
    return list(MODE_REGISTRY.keys())


def require_mode(mode_name: str) -> Dict[str, object]:
    if mode_name not in MODE_REGISTRY:
        raise ValueError("未知模式：%s" % mode_name)
    return MODE_REGISTRY[mode_name]


def build_system_prompt(mode_name: str) -> str:
    config = require_mode(mode_name)
    allowed_tools = list(config["allowed_tools"]) + ["switch_mode"]
    writable_globs = config["writable_globs"]
    writable_text = ", ".join(writable_globs) if writable_globs else "只读"
    return (
        "你是 EmbedAgent 的受控模式原型。"
        "请优先用中文回答，并严格遵守当前模式边界。"
        "当任务需要当前模式之外的工具时，先调用 switch_mode。\n\n"
        "当前模式：%s\n"
        "模式说明：%s\n"
        "允许工具：%s\n"
        "可写范围：%s"
    ) % (
        mode_name,
        config["system_prompt"],
        ", ".join(allowed_tools),
        writable_text,
    )


def allowed_tools_for(mode_name: str) -> List[str]:
    config = require_mode(mode_name)
    return list(config["allowed_tools"]) + ["switch_mode"]


def is_tool_allowed(mode_name: str, tool_name: str) -> bool:
    return tool_name in allowed_tools_for(mode_name)


def is_path_writable(mode_name: str, relative_path: str) -> bool:
    config = require_mode(mode_name)
    normalized_path = relative_path.replace("\\", "/")
    for pattern in config["writable_globs"]:
        if fnmatch.fnmatch(normalized_path, pattern):
            return True
    return False


def switch_mode_schema() -> Dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": "switch_mode",
            "description": "切换当前工作模式。用于在澄清、规格、编码、验证和调试阶段之间切换。目标模式必须来自预定义模式列表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "enum": mode_names(),
                        "description": "要切换到的目标模式，必须是受支持的模式名。示例：code",
                    }
                },
                "required": ["target"],
                "additionalProperties": False,
            },
        },
    }


def parse_mode_command(text: str, fallback_mode: str = DEFAULT_MODE) -> Tuple[str, str, bool]:
    stripped = text.strip()
    if not stripped:
        return fallback_mode, text, False
    match = _MODE_COMMAND_RE.match(stripped)
    if not match:
        return fallback_mode, text, False
    target = match.group(1)
    require_mode(target)
    remainder = (match.group(2) or "").strip()
    return target, remainder, True
