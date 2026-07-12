from __future__ import annotations

import re
from typing import List, Optional, Tuple

_DENY_PATTERNS = (
    r"\brm\s+(-[a-z]*r[a-z]*f[a-z]*|-[a-z]*f[a-z]*r[a-z]*)\b",
    r"\brmdir\s+/s\b",
    r"\bdel\s+/[sf]",
    r"\brd\s+/s\b",
    r"\bformat\s+[a-z]:",
    r"\bdiskpart\b",
    r"\breg\s+(delete|add)\b",
    r"\bregedit\b",
    r"\bnet\s+(user|localgroup)\b",
    r"\b(useradd|userdel|passwd|sudo|killall|shutdown|reboot|iptables)\b",
    r"\bchmod\s+777\b",
    r"\bkill\s+-9\b",
    r"\btaskkill\s+(/[a-z]+\s+)*/(im|f)\b",
    r"\bnetsh\s+(firewall|advfirewall)\b",
    r">\s*/dev/sd[a-z]",
    r">\s*[a-z]:\\(windows|system32)",
)


class CommandSanitizer(object):
    def __init__(self, extra_deny_patterns: Optional[List[str]] = None) -> None:
        self._deny = [re.compile(item, re.IGNORECASE) for item in _DENY_PATTERNS]
        self._deny.extend(re.compile(item, re.IGNORECASE) for item in (extra_deny_patterns or []))

    def is_blocked(self, command: str) -> Tuple[bool, str]:
        for pattern in self._deny:
            match = pattern.search(command)
            if match:
                return True, "命令包含被禁止的操作模式（%r），已拒绝执行。" % match.group(0)
        return False, ""
