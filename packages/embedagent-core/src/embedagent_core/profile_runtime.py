from __future__ import annotations

import fnmatch
from typing import Any, Dict, List, Tuple

PROFILE_PROMPT_FRAME = (
    "You are operating under an explicit agent mode. Follow the current mode "
    "boundary and answer in the user's language. Mode selection does not grant "
    "permissions; runtime permission and write-path policies remain authoritative.\n\n"
    "Current mode: {mode_name}\n"
    "Mode description: {mode_description}\n"
    "User confirmation: {ask_rule}\n"
    "Writable paths: {writable_globs}"
)

BASE_READ_TOOLS = ["read_file", "list_dir", "glob_files", "grep_text"]
BASE_DISCUSSION_TOOLS = BASE_READ_TOOLS + ["git_status", "git_log", "ask_user"]
BASE_WRITE_TOOLS = BASE_READ_TOOLS + [
    "write_file",
    "edit_file",
    "bash",
    "author_local_capability",
    "ask_user",
]
BASE_VERIFY_TOOLS = BASE_READ_TOOLS + ["bash", "ask_user"]
SPEC_WRITABLE_GLOBS = ["**/*.md", "**/*.rst", "**/*.txt"]


def _fnmatch_with_doublestar(path: str, pattern: str) -> bool:
    if fnmatch.fnmatch(path, pattern):
        return True
    if pattern.startswith("**/") and fnmatch.fnmatch(path, pattern[3:]):
        return True
    return False


def profile_writable_globs(profile: Any, mode_name: str, config: Any = None) -> List[str]:
    base_globs = list(profile.writable_globs_for(mode_name))
    if config is not None:
        override = getattr(config, "mode_writable_globs", {}).get(mode_name)
        if override is not None and isinstance(override, list):
            base_globs = list(override)
        extra = getattr(config, "mode_extra_writable_globs", {}).get(mode_name)
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


class AgentProfileToolPolicy(object):
    def __init__(self, profile: Any = None) -> None:
        self._profile = profile

    def allowed_tools_for(self, mode_name: str, workflow_state: Any = None) -> List[str]:
        del workflow_state
        if self._profile is None:
            return []
        return self._profile.allowed_tools_for(mode_name)


class AgentProfileWritePathPolicy(object):
    def __init__(self, profile: Any) -> None:
        self._profile = profile

    def is_path_writable(
        self,
        mode_name: str,
        normalized_path: str,
        app_config: Any = None,
    ) -> bool:
        path = normalized_path.replace("\\", "/")
        result = False
        for raw_pattern in profile_writable_globs(self._profile, mode_name, app_config):
            pattern = raw_pattern.replace("\\", "/")
            if pattern.startswith("!"):
                if _fnmatch_with_doublestar(path, pattern[1:]):
                    result = False
            elif _fnmatch_with_doublestar(path, pattern):
                result = True
        return result


class AgentProfileRuntimePolicy(object):
    def __init__(self, profile: Any) -> None:
        self._profile = profile

    def default_mode(self) -> str:
        return str(self._profile.default_mode)

    def require_mode(self, mode_name: str) -> Dict[str, Any]:
        return self._profile.require_mode(mode_name or self.default_mode()).to_mode_definition()

    def build_system_prompt(
        self,
        mode_name: str,
        app_config: Any = None,
        workspace: str = "",
        local_resources: Any = None,
    ) -> str:
        mode = self._profile.require_mode(mode_name or self.default_mode())
        allowed_tools = list(mode.allowed_tools)
        writable_globs = profile_writable_globs(self._profile, mode.slug, app_config)
        writable_text = ", ".join(writable_globs) if writable_globs else "read-only"
        can_ask_user = "ask_user" in allowed_tools
        ask_rule = (
            "Offer clear options and wait for confirmation when a key decision is missing."
            if can_ask_user
            else "Explain the decision in natural language and wait for user input."
        )
        del workspace, local_resources
        return PROFILE_PROMPT_FRAME.format(
            mode_name=mode.slug,
            mode_description=str(mode.system_prompt),
            ask_rule=ask_rule,
            writable_globs=writable_text,
        )

    def parse_mode_switch_request(
        self,
        user_text: str,
        fallback_mode: str,
    ) -> Tuple[str, str, bool]:
        fallback = fallback_mode or self.default_mode()
        stripped = str(user_text or "").strip()
        if not stripped:
            return fallback, user_text, False
        parts = stripped.split(None, 2)
        if parts and parts[0] == "/mode" and len(parts) >= 2:
            resolved = self.require_mode(parts[1])["slug"]
            remainder = parts[2].strip() if len(parts) >= 3 else ""
            return str(resolved), remainder, True
        lowered = stripped.lower()
        prefixes = (
            "切换到",
            "切到",
            "进入",
            "转到",
            "switch to ",
            "switch mode ",
            "change to ",
            "change mode ",
        )
        if not any(lowered.startswith(prefix.lower()) for prefix in prefixes):
            return fallback, user_text, False
        for mode in self._profile.modes:
            mode_text = str(mode.slug or "").strip()
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
                return mode.slug, "", True
        return fallback, user_text, False
