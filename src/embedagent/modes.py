from __future__ import annotations

import fnmatch
import json
import logging
import os
import re
from typing import Dict, List, Optional, Tuple

_LOG = logging.getLogger(__name__)

DEFAULT_MODE = "explore"

# ---------------------------------------------------------------------------
# Prompt frame template — can be overridden at ~/.embedagent/prompt_frame.txt
# Placeholders: {mode_name} {mode_description} {ask_rule} {allowed_tools} {writable_globs}
# Use {{ and }} to include literal braces in an override file.
# ---------------------------------------------------------------------------
_DEFAULT_PROMPT_FRAME = (
    "你是 EmbedAgent 的受控模式原型。"
    "请优先用中文回答，并严格遵守当前模式边界。"
    "模式不是权限系统；权限审批由运行时单独处理。"
    "工程结构是可探测的软约定，不是你必须强推的模板。\n\n"
    "当前模式：{mode_name}\n"
    "模式说明：{mode_description}\n"
    "模式切换规则：你不能主动切换模式。若需要切换，用 ask_user 向用户提供选项（含 option_N_mode 字段），由用户确认后切换；或建议用户使用 /mode 命令。\n"
    "用户确认规则：{ask_rule}\n"
    "允许工具：{allowed_tools}\n"
    "可写范围：{writable_globs}"
)

# ---------------------------------------------------------------------------
# Built-in mode definitions (5 modes for C maintenance workflow)
# All modes include manage_todos + ask_user for consistency.
# switch_mode is intentionally NOT in any mode's allowed_tools —
# mode switching is exclusively user-driven (/mode command or ask_user options).
# ---------------------------------------------------------------------------
_BUILTIN_MODES = {
    "explore": {
        "slug": "explore",
        "system_prompt": (
            "你当前处于 explore 模式（默认模式）。"
            "负责阅读代码、解释逻辑、讨论设计方案，以及帮助用户理清思路。"
            "任务开始时先用 manage_todos list 查看未完成项，有任务则先向用户汇报。"
            "当用户需要修改文件时，用 ask_user 询问应切换到哪个模式，"
            "提供 2-4 个选项（如 spec / code / debug），等待用户用 /mode 切换。"
            "不要擅自写文件。"
        ),
        "allowed_tools": ["read_file", "list_files", "search_text",
                          "git_status", "git_log",
                          "manage_todos", "ask_user"],
        "writable_globs": [],
    },
    "spec": {
        "slug": "spec",
        "system_prompt": (
            "你当前处于 spec 模式，负责整理需求、边界条件、验收标准和文档。"
            "先用 list_files 探测现有文档目录；若工作区为空或无文档目录，可在 docs/ 下创建。"
            "任务开始时用 manage_todos list 查看待办项，完成后及时标记。"
            "不要擅自切到实现模式；若需要实现，用 ask_user 告知用户。"
        ),
        "allowed_tools": ["read_file", "list_files", "search_text",
                          "write_file", "manage_todos", "ask_user"],
        "writable_globs": ["**/*.md", "**/*.rst", "**/*.txt"],
    },
    "code": {
        "slug": "code",
        "system_prompt": (
            "你当前处于 code 模式，负责以最小变更实现代码。"
            "应复用现有工程结构，不要假设 src/ 必然存在；先用 list_files 了解目录布局。"
            "任务开始时用 manage_todos list 查看待办项，完成阶段性工作后标记已完成。"
            "若遇到需要用户决策的问题，用 ask_user 询问。"
        ),
        "allowed_tools": ["read_file", "list_files", "write_file", "edit_file",
                          "search_text", "compile_project",
                          "git_status", "git_diff",
                          "manage_todos", "ask_user"],
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
    "debug": {
        "slug": "debug",
        "system_prompt": (
            "你当前处于 debug 模式，负责复现问题、定位根因并做最小修复。"
            "先根据当前工程结构和诊断缩小范围，不要假设固定目录。"
            "任务开始时用 manage_todos list 查看待办项。"
            "若需要更大范围重构，用 ask_user 告知用户建议切换到 code 模式。"
        ),
        "allowed_tools": ["read_file", "list_files", "search_text",
                          "write_file", "edit_file", "run_command",
                          "git_status", "git_diff", "git_log",
                          "manage_todos", "ask_user"],
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
    "verify": {
        "slug": "verify",
        "system_prompt": (
            "你当前处于 verify 模式，负责执行构建、测试、静态检查并给出质量门结论。"
            "本模式不改代码；发现问题时只说明证据与建议，用 ask_user 告知用户需要切换到哪个模式修复。"
            "任务开始时用 manage_todos list 查看待办项。"
        ),
        "allowed_tools": ["compile_project", "run_tests", "run_clang_tidy",
                          "report_quality", "manage_todos", "ask_user"],
        "writable_globs": [],
    },
}  # type: Dict[str, Dict[str, object]]

# Public registry — rebuilt by initialize_modes(); tests that import directly
# get the built-in defaults without calling initialize_modes().
MODE_REGISTRY = dict(_BUILTIN_MODES)  # type: Dict[str, Dict[str, object]]

_MODE_COMMAND_RE = re.compile(r"^/mode\s+(\w+)(?:\s+(.*))?$", re.DOTALL)


# ---------------------------------------------------------------------------
# Config-driven initialization
# ---------------------------------------------------------------------------

def load_modes_config(workspace: str) -> Dict[str, Dict[str, object]]:
    """Load mode overrides from user-level and project-level modes.json.

    Returns a dict mapping mode_name -> full mode definition dict.
    Each entry in the config fully replaces the corresponding built-in mode.
    Modes only in config (not in _BUILTIN_MODES) are added as new custom modes.
    """
    user_path = os.path.join(os.path.expanduser("~"), ".embedagent", "modes.json")
    project_path = os.path.join(workspace, ".embedagent", "modes.json")
    merged = {}  # type: Dict[str, Dict[str, object]]
    for path in (user_path, project_path):
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (IOError, OSError, ValueError) as exc:
            _LOG.warning("Failed to load modes config %s: %s", path, exc)
            continue
        if not isinstance(data, dict):
            continue
        modes_data = data.get("modes")
        if not isinstance(modes_data, dict):
            continue
        for mode_name, mode_def in modes_data.items():
            if not isinstance(mode_def, dict):
                continue
            slug = str(mode_name)
            entry = dict(mode_def)
            entry["slug"] = slug
            # Ensure required keys are present, falling back to built-in if partial
            builtin = _BUILTIN_MODES.get(slug, {})
            if "system_prompt" not in entry:
                entry["system_prompt"] = builtin.get("system_prompt", "")
            if "allowed_tools" not in entry:
                entry["allowed_tools"] = list(builtin.get("allowed_tools", []))
            if "writable_globs" not in entry:
                entry["writable_globs"] = list(builtin.get("writable_globs", []))
            merged[slug] = entry
    return merged


def initialize_modes(workspace: str) -> None:
    """Rebuild MODE_REGISTRY from built-ins merged with config-file overrides.

    Call once at startup (cli.py, inprocess_adapter.__init__) before any
    require_mode() calls that should see project-level customizations.
    Safe to call multiple times; later calls overwrite earlier state.
    """
    global MODE_REGISTRY
    overrides = load_modes_config(workspace)
    new_registry = dict(_BUILTIN_MODES)
    new_registry.update(overrides)
    MODE_REGISTRY = new_registry


# ---------------------------------------------------------------------------
# Prompt frame loading
# ---------------------------------------------------------------------------

def _load_prompt_frame() -> str:
    """Return the prompt frame template, preferring ~/.embedagent/prompt_frame.txt."""
    user_frame = os.path.join(os.path.expanduser("~"), ".embedagent", "prompt_frame.txt")
    if os.path.isfile(user_frame):
        try:
            with open(user_frame, "r", encoding="utf-8") as fh:
                content = fh.read()
            if content.strip():
                return content
        except (IOError, OSError):
            pass
    return _DEFAULT_PROMPT_FRAME


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def mode_names() -> List[str]:
    return list(MODE_REGISTRY.keys())


def require_mode(mode_name: str) -> Dict[str, object]:
    """Return the mode dict for mode_name.

    Unlike the previous implementation, unknown mode slugs no longer raise
    ValueError — they fall back to DEFAULT_MODE with a warning.  This prevents
    crashes when resuming old sessions that referenced since-deleted modes
    (e.g. 'orchestra', 'ask', 'compact').
    """
    if mode_name in MODE_REGISTRY:
        return MODE_REGISTRY[mode_name]
    _LOG.warning("Unknown mode %r, falling back to %r", mode_name, DEFAULT_MODE)
    return MODE_REGISTRY[DEFAULT_MODE]


def get_writable_globs(mode_name: str, config=None) -> List[str]:
    """Return writable globs for a mode, applying per-project config overrides.

    Args:
        mode_name: Name of the mode.
        config: Optional AppConfig. When config contains a mode_writable_globs
                entry for this mode, that list replaces the built-in default.
    """
    base_globs = list(require_mode(mode_name)["writable_globs"])  # type: ignore[index]
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
    allowed_tools = list(cfg["allowed_tools"])  # type: ignore[index]
    writable_globs = get_writable_globs(mode_name, config)
    writable_text = ", ".join(writable_globs) if writable_globs else "只读"
    can_ask_user = "ask_user" in allowed_tools
    ask_rule = (
        "当缺少关键决策时，优先用 ask_user 提供 2 到 4 个明确选项（可含 option_N_mode 触发模式切换）。"
        if can_ask_user
        else "当需要用户决策时，用自然语言说明建议并等待用户输入。"
    )
    frame = _load_prompt_frame()
    return frame.format(
        mode_name=mode_name,
        mode_description=str(cfg["system_prompt"]),
        ask_rule=ask_rule,
        allowed_tools=", ".join(allowed_tools),
        writable_globs=writable_text,
    )


def allowed_tools_for(mode_name: str) -> List[str]:
    cfg = require_mode(mode_name)
    return list(cfg["allowed_tools"])  # type: ignore[index]


def is_tool_allowed(mode_name: str, tool_name: str) -> bool:
    return tool_name in allowed_tools_for(mode_name)


def _fnmatch_with_doublestar(path: str, pattern: str) -> bool:
    """Return True if *path* matches *pattern*.

    Handles the ``**/`` prefix as "any depth, including zero" because
    Python's :mod:`fnmatch` does not natively support ``**``.
    """
    if fnmatch.fnmatch(path, pattern):
        return True
    if pattern.startswith("**/") and fnmatch.fnmatch(path, pattern[3:]):
        return True
    return False


def is_path_writable(mode_name: str, relative_path: str, config=None) -> bool:
    """Return True if *relative_path* is writable in *mode_name*.

    Glob patterns are evaluated in order; the **last matching** pattern wins
    (`.gitignore` semantics).  A pattern prefixed with ``!`` is a negation
    rule that revokes write permission for paths that match it::

        writable_globs:
          - "**/*.c"      # allow all C files
          - "!build/**"   # except anything under build/

    This lets projects exclude generated files (e.g. ``build/``) from the
    writable set without enumerating every non-build directory.
    """
    normalized_path = relative_path.replace("\\", "/")
    result = False  # default: not writable
    for raw_pattern in get_writable_globs(mode_name, config):
        raw_pattern = raw_pattern.replace("\\", "/")
        if raw_pattern.startswith("!"):
            # Negation: if this pattern matches, revoke permission.
            deny_pattern = raw_pattern[1:]
            if _fnmatch_with_doublestar(normalized_path, deny_pattern):
                result = False
        else:
            if _fnmatch_with_doublestar(normalized_path, raw_pattern):
                result = True
    return result


def parse_mode_command(text: str, fallback_mode: str = DEFAULT_MODE) -> Tuple[str, str, bool]:
    stripped = text.strip()
    if not stripped:
        return fallback_mode, text, False
    match = _MODE_COMMAND_RE.match(stripped)
    if not match:
        return fallback_mode, text, False
    target = match.group(1)
    # Use require_mode's fallback behaviour instead of raising
    resolved = require_mode(target)["slug"]  # type: ignore[index]
    remainder = (match.group(2) or "").strip()
    return str(resolved), remainder, True
