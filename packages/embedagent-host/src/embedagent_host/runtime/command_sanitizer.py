from __future__ import annotations

import re
from typing import List, Optional, Tuple

_RAW_DENY_PATTERNS = (
    r"\brm\s+(-[a-z]*r[a-z]*f[a-z]*|-[a-z]*f[a-z]*r[a-z]*)\b",
    r"\brmdir\s+/s\b",
    r"\bdel\s+/[sf]",
    r"\brd\s+/s\b",
    r"\bformat\s+[a-z]:",
    r"\bdiskpart\b",
    r"\breg\s+(delete|add)\b",
    r"\bregedit\b",
    r"\bnet\s+user\b",
    r"\bnet\s+localgroup\b",
    r"\buseradd\b",
    r"\buserdel\b",
    r"\bpasswd\b",
    r"\bchmod\s+777\b",
    r"\bsudo\b",
    r"\bsu\s+-\S*",
    r"\btaskkill\s+(/[a-z]+\s+)*/(im|f)\b",
    r"\bkill\s+-9\b",
    r"\bkillall\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\binit\s+[0-6]\b",
    r"\bnetsh\s+(firewall|advfirewall)\b",
    r"\biptables\b",
    r">\s*/dev/sd[a-z]",
    r">\s*[a-z]:\\(windows|system32)",
)

_RAW_CAUTION_PATTERNS = (
    r"\|\s*sh\b",
    r"\|\s*bash\b",
    r"\|\s*cmd\b",
    r"\beval\b",
    r"\bexec\b",
    r">\s*[^\s]",
    r"&&",
    r";\s*\S",
    r"\$\(",
    r"`[^`]+`",
    r"\bcurl\b.*\|\s*(bash|sh)\b",
    r"\bwget\b.*\|\s*(bash|sh)\b",
    r"\bpython\b.*-c\b",
    r"\bpowershell\b.*-[eE][nN][cC]",
)

BUILTIN_DENY_PATTERNS = [re.compile(item, re.IGNORECASE) for item in _RAW_DENY_PATTERNS]
BUILTIN_CAUTION_PATTERNS = [re.compile(item, re.IGNORECASE) for item in _RAW_CAUTION_PATTERNS]


class CommandSanitizer(object):
    def __init__(
        self,
        extra_deny_patterns: Optional[List[str]] = None,
        extra_caution_patterns: Optional[List[str]] = None,
    ) -> None:
        self._deny = list(BUILTIN_DENY_PATTERNS)
        self._caution = list(BUILTIN_CAUTION_PATTERNS)
        self._deny.extend(re.compile(item, re.IGNORECASE) for item in (extra_deny_patterns or []))
        self._caution.extend(
            re.compile(item, re.IGNORECASE) for item in (extra_caution_patterns or [])
        )

    def is_blocked(self, command: str) -> Tuple[bool, str]:
        for pattern in self._deny:
            match = pattern.search(command)
            if match:
                return True, "命令包含被禁止的操作模式（%r），已拒绝执行。" % match.group(0)
        return False, ""

    def caution_note(self, command: str) -> Tuple[bool, str]:
        matches = []
        for pattern in self._caution:
            match = pattern.search(command)
            if match:
                matches.append(match.group(0))
        if not matches:
            return False, ""
        note = "命令包含复合操作符（%s），执行前请确认安全性。" % "、".join(
            repr(item) for item in matches[:3]
        )
        return True, note
