from __future__ import annotations

import fnmatch
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from embedagent.agent_profiles import generic_agent_profile
from embedagent.di_container import get_default_container

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
    "模式切换规则：你不能主动切换模式。若需要切换，向用户提供明确选项并等待确认；或建议用户使用 /mode 命令。\n"
    "用户确认规则：{ask_rule}\n"
    "写入边界：{writable_globs}"
)

# ---------------------------------------------------------------------------
# Built-in mode definitions come from the global/base agent profile.
# Selected AgentApplication profiles provide specialized hosted mode policy.
# Workflow packages add scenario tools through the extension boundary.
# ---------------------------------------------------------------------------
_DEFAULT_AGENT_PROFILE = generic_agent_profile()
_BUILTIN_MODES = _DEFAULT_AGENT_PROFILE.mode_registry()

_MODE_COMMAND_RE = re.compile(r"^/mode\s+(\w+)(?:\s+(.*))?$", re.DOTALL)
_NATURAL_MODE_SWITCH_PREFIX_RE = re.compile(
    r"^\s*(?:切换到|切到|进入|转到|switch\s+(?:to\s+)?|change\s+(?:to\s+)?)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# PermissionContract — mode as permission contract, not workflow track
# ---------------------------------------------------------------------------


@dataclass
class PermissionContract:
    """Defines what a mode allows without prescribing workflow.

    This replaces the old 'track' concept where modes had fixed
    workflow steps. Now modes only specify:
    - Which tools are available
    - Which tools require explicit permission
    - Which files can be written
    """

    mode_name: str
    allowed_tools: List[str] = field(default_factory=list)
    permission_required_tools: List[str] = field(default_factory=list)
    writable_globs: List[str] = field(default_factory=list)
    read_only: bool = False

    def allows_tool(self, tool_name: str) -> bool:
        """Check if a tool is allowed in this mode."""
        if not self.allowed_tools:
            return True
        return tool_name in self.allowed_tools

    def requires_permission(self, tool_name: str) -> bool:
        """Check if a tool requires explicit user permission."""
        return tool_name in self.permission_required_tools

    def is_path_writable(self, path: str) -> bool:
        """Check if a path is writable in this mode."""
        if self.read_only:
            return False
        # Check against writable globs
        for pattern in self.writable_globs:
            if _fnmatch_with_doublestar(path, pattern):
                return True
        return False


def _build_mode_contracts() -> Dict[str, PermissionContract]:
    """Build PermissionContract instances from built-in mode definitions."""
    contracts = {}
    for mode_name, mode_def in _BUILTIN_MODES.items():
        allowed_tools = list(mode_def.get("allowed_tools", []))
        writable_globs = list(mode_def.get("writable_globs", []))
        read_only = not bool(writable_globs)
        permission_required = []
        if mode_name == "build":
            permission_required = ["write_file", "edit_file"]
        elif mode_name == "debug":
            permission_required = ["edit_file"]
        contracts[mode_name] = PermissionContract(
            mode_name=mode_name,
            allowed_tools=allowed_tools,
            permission_required_tools=permission_required,
            writable_globs=writable_globs,
            read_only=read_only,
        )
    return contracts


MODE_CONTRACTS = _build_mode_contracts()


def get_mode_contract(mode_name: str) -> PermissionContract:
    """Get the permission contract for a mode."""
    return MODE_CONTRACTS.get(
        mode_name,
        MODE_CONTRACTS.get("explore", PermissionContract(mode_name="explore", read_only=True)),
    )


# ---------------------------------------------------------------------------
# Factory-based registry
# ---------------------------------------------------------------------------


def get_mode_registry(fresh: bool = False) -> Dict[str, Any]:
    """Return the mode registry.

    Use fresh=True in tests to get an isolated registry.
    """
    if fresh:
        return {}
    return get_default_container().resolve("mode_registry", fresh=False)


def initialize_modes(
    workspace: str = "", registry: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Rebuild mode registry from built-ins merged with config-file overrides.

    Args:
        workspace: Path to workspace for loading config overrides.
        registry: Optional explicit registry to mutate. If None, a fresh
            registry is created and registered in the DI container.

    Returns:
        The populated mode registry dict.
    """
    if registry is None:
        registry = dict(_BUILTIN_MODES)
        overrides = load_modes_config(workspace)
        registry.update(overrides)
        # Register in container for singleton access
        container = get_default_container()
        container.register_factory("mode_registry", lambda: registry)
        return registry
    else:
        # When an explicit registry is passed, just populate it
        for name, definition in _BUILTIN_MODES.items():
            registry[name] = definition
        return registry


# Register factory on module load
_get_mode_registry_original = get_mode_registry


def _register_mode_factory() -> None:
    container = get_default_container()
    container.register_factory("mode_registry", lambda: initialize_modes())


_register_mode_factory()


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


def _load_project_context(workspace: str) -> str:
    """Load project-specific context from .embedagent/context.md if present."""
    if not workspace:
        return ""
    ctx_path = os.path.join(workspace, ".embedagent", "context.md")
    try:
        with open(ctx_path, encoding="utf-8") as fh:
            return fh.read().strip()
    except (FileNotFoundError, OSError):
        return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def mode_names() -> List[str]:
    return list(get_mode_registry().keys())


def require_mode(mode_name: str) -> Dict[str, object]:
    """Return the mode dict for mode_name.

    Unknown mode slugs raise ``ValueError`` immediately.
    """
    registry = get_mode_registry()
    if mode_name in registry:
        return registry[mode_name]
    raise ValueError("Unknown mode %r" % (mode_name,))


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


def build_system_prompt(
    mode_name: str, config=None, workspace: str = "", local_resources=None
) -> str:
    cfg = require_mode(mode_name)
    allowed_tools = list(cfg["allowed_tools"])  # type: ignore[index]
    writable_globs = get_writable_globs(mode_name, config)
    writable_text = ", ".join(writable_globs) if writable_globs else "只读"
    can_ask_user = "ask_user" in allowed_tools
    ask_rule = (
        "当缺少关键决策时，向用户提供 2 到 4 个明确选项并等待确认。"
        if can_ask_user
        else "当需要用户决策时，用自然语言说明建议并等待用户输入。"
    )
    frame = _load_prompt_frame()
    result = frame.format(
        mode_name=mode_name,
        mode_description=str(cfg["system_prompt"]),
        ask_rule=ask_rule,
        allowed_tools=", ".join(allowed_tools),
        writable_globs=writable_text,
    )
    ctx = _load_project_context(workspace)
    if ctx:
        result += "\n\n## Project Context\n" + ctx
    del local_resources  # Resource listings are injected by the hosted prompt surface.
    return result


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
    resolved = require_mode(target)["slug"]  # type: ignore[index]
    remainder = (match.group(2) or "").strip()
    return str(resolved), remainder, True


def parse_natural_language_mode_switch(
    text: str, fallback_mode: str = DEFAULT_MODE
) -> Tuple[str, str, bool]:
    stripped = str(text or "").strip()
    if not stripped:
        return fallback_mode, text, False
    if _NATURAL_MODE_SWITCH_PREFIX_RE.match(stripped) is None:
        return fallback_mode, text, False
    lowered = stripped.lower()
    for mode_name in mode_names():
        mode_text = str(mode_name or "").strip()
        if not mode_text:
            continue
        candidates = (
            "切换到%s模式" % mode_text,
            "切换到%s" % mode_text,
            "切到%s模式" % mode_text,
            "切到%s" % mode_text,
            "进入%s模式" % mode_text,
            "进入%s" % mode_text,
            "转到%s模式" % mode_text,
            "转到%s" % mode_text,
            "switch to %s mode" % mode_text,
            "switch to %s" % mode_text,
            "switch mode %s" % mode_text,
            "change to %s mode" % mode_text,
            "change to %s" % mode_text,
            "change mode %s" % mode_text,
        )
        if lowered in [candidate.lower() for candidate in candidates]:
            resolved = require_mode(mode_text)["slug"]  # type: ignore[index]
            return str(resolved), "", True
    return fallback_mode, text, False
