from __future__ import annotations

import fnmatch
import re
from typing import Dict, List, Optional, Tuple


DEFAULT_MODE = "code"

# 可写路径使用扩展名通配符而不绑定目录结构，兼容任意项目布局。
# 如需限制到特定目录，可在项目级 .embedagent/config.json 的
# mode_writable_globs 字段覆盖。
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
        "allowed_tools": ["read_file", "list_files", "search_text", "manage_todos"],
        "writable_globs": [],
    },
    "spec": {
        "slug": "spec",
        "system_prompt": "你当前处于 spec 模式，负责整理需求、边界条件、验收标准和文档，不直接承担命令执行或开放式调试。修改范围应限制在文档文件。",
        "allowed_tools": ["read_file", "list_files", "search_text", "edit_file"],
        "writable_globs": ["**/*.md", "**/*.rst", "**/*.txt"],
    },
    "code": {
        "slug": "code",
        "system_prompt": "你当前处于 code 模式，负责以最小变更实现代码。优先使用 compile_project 做编译验证，而不是泛化命令执行。",
        "allowed_tools": ["read_file", "list_files", "edit_file", "search_text", "compile_project", "manage_todos"],
        "writable_globs": [
            "**/*.c", "**/*.h",
            "**/*.py", "**/*.pyi",
            "**/*.toml", "**/*.cfg", "**/*.ini",
        ],
    },
    "test": {
        "slug": "test",
        "system_prompt": "你当前处于 test 模式，负责编写或调整测试入口、验证脚本和测试辅助代码。优先让问题可复现，并使用 run_tests 形成闭环。",
        "allowed_tools": ["read_file", "edit_file", "search_text", "run_tests"],
        "writable_globs": ["**/*.c", "**/*.h", "**/*.py", "**/*.pyi"],
    },
    "verify": {
        "slug": "verify",
        "system_prompt": "你当前处于 verify 模式，负责执行构建、测试、静态检查并给出质量门结论，不直接编辑源码。若发现需要改动，请切换到 code 或 debug。",
        "allowed_tools": ["compile_project", "run_tests", "run_clang_tidy", "report_quality"],
        "writable_globs": [],
    },
    "debug": {
        "slug": "debug",
        "system_prompt": "你当前处于 debug 模式，负责复现问题、定位根因并做最小修复。优先用读取、搜索和最小命令验证缩小范围。",
        "allowed_tools": ["read_file", "search_text", "edit_file", "run_command"],
        "writable_globs": ["**/*.c", "**/*.h", "**/*.py", "**/*.pyi"],
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


def get_writable_globs(mode_name: str, config=None) -> List[str]:
    """Return writable globs for a mode, applying per-project config overrides.

    Args:
        mode_name: Name of the mode.
        config: Optional AppConfig from embedagent.config. When the config
                contains a mode_writable_globs entry for this mode, that list
                replaces the built-in default entirely.
    """
    base_globs = list(require_mode(mode_name)["writable_globs"])
    if config is None:
        return base_globs
    override = config.mode_writable_globs.get(mode_name)
    if override is not None and isinstance(override, list):
        return list(override)
    return base_globs


def build_system_prompt(mode_name: str, config=None) -> str:
    cfg = require_mode(mode_name)
    allowed_tools = list(cfg["allowed_tools"]) + ["switch_mode"]
    writable_globs = get_writable_globs(mode_name, config)
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
        cfg["system_prompt"],
        ", ".join(allowed_tools),
        writable_text,
    )


def allowed_tools_for(mode_name: str) -> List[str]:
    cfg = require_mode(mode_name)
    return list(cfg["allowed_tools"]) + ["switch_mode"]


def is_tool_allowed(mode_name: str, tool_name: str) -> bool:
    return tool_name in allowed_tools_for(mode_name)


def is_path_writable(mode_name: str, relative_path: str, config=None) -> bool:
    normalized_path = relative_path.replace("\\", "/")
    for pattern in get_writable_globs(mode_name, config):
        normalized_pattern = pattern.replace("\\", "/")
        if fnmatch.fnmatch(normalized_path, normalized_pattern):
            return True
        # Python 的 fnmatch 不会让 "**/*.md" 匹配根目录 README.md，
        # 这里把前导 "**/" 视为“任意子目录，可为空”。
        if normalized_pattern.startswith("**/") and fnmatch.fnmatch(
            normalized_path,
            normalized_pattern[3:],
        ):
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
