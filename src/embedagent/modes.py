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
        "system_prompt": "你当前处于 ask 模式，只负责澄清信息缺口、边界与关键决策。不要实现功能，也不要主动切模式；需要方向时用 ask_user 向用户确认。",
        "allowed_tools": ["read_file", "list_files", "search_text", "ask_user"],
        "writable_globs": [],
    },
    "orchestra": {
        "slug": "orchestra",
        "system_prompt": "你当前处于 orchestra 模式，负责拆解任务、协调步骤，并在明确理由时把工作路由到下游模式。只有本模式可以主动调用 switch_mode。",
        "allowed_tools": ["read_file", "list_files", "search_text", "manage_todos", "ask_user", "switch_mode"],
        "writable_globs": [],
    },
    "spec": {
        "slug": "spec",
        "system_prompt": "你当前处于 spec 模式，负责整理需求、边界条件、验收标准和文档。先复用现有文档结构；若工作区没有文档目录，可轻量创建 docs/，但不要擅自切到实现模式。",
        "allowed_tools": ["read_file", "list_files", "search_text", "write_file", "ask_user"],
        "writable_globs": ["**/*.md", "**/*.rst", "**/*.txt"],
    },
    "code": {
        "slug": "code",
        "system_prompt": "你当前处于 code 模式，负责以最小变更实现代码。应复用现有工程结构，不要假设 src/ 必然存在；若需要其它模式，请先完成当前职责并向用户说明。",
        "allowed_tools": ["read_file", "list_files", "write_file", "edit_file", "search_text", "compile_project", "manage_todos"],
        "writable_globs": [
            "**/*.c", "**/*.cc", "**/*.cpp", "**/*.cxx",
            "**/*.h", "**/*.hh", "**/*.hpp", "**/*.hxx",
            "**/*.py", "**/*.pyi", "**/*.ps1", "**/*.bat",
            "**/*.toml", "**/*.cfg", "**/*.ini",
            "**/*.json", "**/*.yaml", "**/*.yml",
            "**/*.cmake", "CMakeLists.txt", "**/CMakeLists.txt",
            "Makefile", "**/Makefile", "makefile", "**/makefile",
            "meson.build", "**/meson.build",
        ],
    },
    "test": {
        "slug": "test",
        "system_prompt": "你当前处于 test 模式，负责编写或调整测试入口、夹具和验证脚本。优先让问题可复现，不要假设 tests/ 必然存在。",
        "allowed_tools": ["read_file", "write_file", "edit_file", "search_text", "run_tests"],
        "writable_globs": [
            "**/*.c", "**/*.cc", "**/*.cpp", "**/*.cxx",
            "**/*.h", "**/*.hh", "**/*.hpp", "**/*.hxx",
            "**/*.py", "**/*.pyi", "**/*.json",
            "**/*.yaml", "**/*.yml", "**/*.txt",
            "**/*.cmake", "CMakeLists.txt", "**/CMakeLists.txt",
        ],
    },
    "verify": {
        "slug": "verify",
        "system_prompt": "你当前处于 verify 模式，负责执行构建、测试、静态检查并给出质量门结论。本模式不改代码，也不自动切模式；发现问题时只说明证据与建议。",
        "allowed_tools": ["compile_project", "run_tests", "run_clang_tidy", "report_quality"],
        "writable_globs": [],
    },
    "debug": {
        "slug": "debug",
        "system_prompt": "你当前处于 debug 模式，负责复现问题、定位根因并做最小修复。先根据当前工程结构和诊断缩小范围，不要假设固定目录，也不要自动切模式。",
        "allowed_tools": ["read_file", "search_text", "write_file", "edit_file", "run_command"],
        "writable_globs": [
            "**/*.c", "**/*.cc", "**/*.cpp", "**/*.cxx",
            "**/*.h", "**/*.hh", "**/*.hpp", "**/*.hxx",
            "**/*.py", "**/*.pyi", "**/*.ps1", "**/*.bat",
            "**/*.toml", "**/*.cfg", "**/*.ini",
            "**/*.json", "**/*.yaml", "**/*.yml",
            "**/*.cmake", "CMakeLists.txt", "**/CMakeLists.txt",
            "Makefile", "**/Makefile", "makefile", "**/makefile",
            "meson.build", "**/meson.build",
        ],
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
        base_globs = list(override)
    extra = config.mode_extra_writable_globs.get(mode_name)
    if extra is not None and isinstance(extra, list):
        base_globs.extend([str(item) for item in extra if str(item or "").strip()])
    deduped = []
    seen = set()
    for item in base_globs:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def build_system_prompt(mode_name: str, config=None) -> str:
    cfg = require_mode(mode_name)
    allowed_tools = list(cfg["allowed_tools"])
    writable_globs = get_writable_globs(mode_name, config)
    writable_text = ", ".join(writable_globs) if writable_globs else "只读"
    can_switch = "switch_mode" in allowed_tools
    can_ask_user = "ask_user" in allowed_tools
    switch_rule = (
        "你可以在理由明确时调用 switch_mode。"
        if can_switch
        else "你不能主动切换模式；若方向需要改变，优先用 ask_user 询问用户，或在回复中建议用户使用 /mode。"
    )
    ask_rule = (
        "当缺少关键决策时，优先用 ask_user 提供 2 到 4 个明确选项。"
        if can_ask_user
        else "当需要用户决策时，用自然语言说明建议并等待用户输入。"
    )
    return (
        "你是 EmbedAgent 的受控模式原型。"
        "请优先用中文回答，并严格遵守当前模式边界。"
        "模式不是权限系统；权限审批由运行时单独处理。"
        "工程结构是可探测的软约定，不是你必须强推的模板。\n\n"
        "当前模式：%s\n"
        "模式说明：%s\n"
        "模式切换规则：%s\n"
        "用户确认规则：%s\n"
        "允许工具：%s\n"
        "可写范围：%s"
    ) % (
        mode_name,
        cfg["system_prompt"],
        switch_rule,
        ask_rule,
        ", ".join(allowed_tools),
        writable_text,
    )


def allowed_tools_for(mode_name: str) -> List[str]:
    cfg = require_mode(mode_name)
    return list(cfg["allowed_tools"])


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
                    },
                    "reason": {
                        "type": "string",
                        "description": "说明为什么此时需要切换模式。示例：规格已明确，下一步进入 code 模式实现。",
                    }
                },
                "required": ["target", "reason"],
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
