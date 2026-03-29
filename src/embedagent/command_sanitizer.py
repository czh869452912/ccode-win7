"""Command safety checks for shell tool execution.

Provides two layers of protection:
  1. BUILTIN_DENY_PATTERNS  — always blocked, regardless of user rules
  2. CAUTION_PATTERNS       — trigger a strengthened confirmation prompt
     (surfaced via the permission system, not blocked outright)

Design notes
------------
* All pattern matching is case-insensitive.
* Patterns are applied to the *full* command string including flags.
* The deny list is intentionally conservative: it targets destructive or
  privilege-escalating operations that have no legitimate agent-initiated
  use case in a code-maintenance workflow.
* New patterns should be added as plain substring matches (str) or
  compiled re.Pattern objects; both are supported.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# Built-in deny list — always blocked
# ---------------------------------------------------------------------------
# Each entry is a regex pattern (case-insensitive).  A command that matches
# ANY of these is rejected before the permission system is even consulted.

_RAW_DENY_PATTERNS: List[str] = [
    # Recursive / forced delete
    r"\brm\s+(-[a-z]*r[a-z]*f[a-z]*|-[a-z]*f[a-z]*r[a-z]*)\b",  # rm -rf / rm -fr
    r"\brmdir\s+/s\b",                                              # Windows: rmdir /s
    r"\bdel\s+/[sf]",                                               # Windows: del /s /f
    r"\brd\s+/s\b",                                                 # Windows: rd /s
    # Disk/volume operations
    r"\bformat\s+[a-z]:",                                           # format C:
    r"\bdiskpart\b",
    # Registry manipulation
    r"\breg\s+(delete|add)\b",
    r"\bregedit\b",
    # User / privilege management
    r"\bnet\s+user\b",
    r"\bnet\s+localgroup\b",
    r"\buseradd\b",
    r"\buserdel\b",
    r"\bpasswd\b",
    r"\bchmod\s+777\b",
    r"\bsudo\b",
    r"\bsu\s+-\b",
    # Process / service kill
    r"\btaskkill\s+(/[a-z]+\s+)*/(im|f)\b",                        # taskkill /F /IM
    r"\bkill\s+-9\b",
    r"\bkillall\b",
    # System shutdown / reboot
    r"\bshutdown\b",
    r"\breboot\b",
    r"\binit\s+[0-6]\b",
    # Network exposure
    r"\bnetsh\s+(firewall|advfirewall)\b",
    r"\biptables\b",
    # Dangerous redirects that overwrite critical paths
    r">\s*/dev/sd[a-z]",
    r">\s*[a-z]:\\(windows|system32)",
]

BUILTIN_DENY_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in _RAW_DENY_PATTERNS
]

# ---------------------------------------------------------------------------
# Caution patterns — returned as a warning annotation, not a hard block
# ---------------------------------------------------------------------------
# These trigger a stronger confirmation message in the permission prompt.

_RAW_CAUTION_PATTERNS: List[str] = [
    r"\|\s*sh\b",                           # pipe into shell
    r"\|\s*bash\b",
    r"\|\s*cmd\b",
    r"\beval\b",
    r"\bexec\b",
    r">\s*[^\s]",                           # any output redirect
    r"&&",                                  # command chaining
    r";\s*\S",                              # command sequencing
    r"\$\(",                                # command substitution
    r"`[^`]+`",                             # backtick substitution
    r"\bcurl\b.*\|\s*(bash|sh)\b",          # curl | bash
    r"\bwget\b.*\|\s*(bash|sh)\b",
    r"\bpython\b.*-c\b",                    # python -c inline exec
    r"\bpowershell\b.*-[eE][nN][cC]",      # base64-encoded PS
]

BUILTIN_CAUTION_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in _RAW_CAUTION_PATTERNS
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class CommandSanitizer(object):
    """Validates a shell command string before execution.

    Usage::

        sanitizer = CommandSanitizer()
        blocked, reason = sanitizer.is_blocked("rm -rf /")
        if blocked:
            return failure_observation(reason)
        caution, note = sanitizer.caution_note("cat file | bash")
    """

    def __init__(
        self,
        extra_deny_patterns: Optional[List[str]] = None,
        extra_caution_patterns: Optional[List[str]] = None,
    ) -> None:
        self._deny: List[re.Pattern] = list(BUILTIN_DENY_PATTERNS)
        self._caution: List[re.Pattern] = list(BUILTIN_CAUTION_PATTERNS)
        for raw in extra_deny_patterns or []:
            self._deny.append(re.compile(raw, re.IGNORECASE))
        for raw in extra_caution_patterns or []:
            self._caution.append(re.compile(raw, re.IGNORECASE))

    def is_blocked(self, command: str) -> Tuple[bool, str]:
        """Return (True, reason) if the command matches a deny pattern.

        Returns (False, "") if the command is acceptable.
        """
        for pattern in self._deny:
            m = pattern.search(command)
            if m:
                return True, (
                    "命令包含被禁止的操作模式（%r），已拒绝执行。" % m.group(0)
                )
        return False, ""

    def caution_note(self, command: str) -> Tuple[bool, str]:
        """Return (True, note) if the command contains a caution pattern.

        Returns (False, "") if no caution pattern matches.  The caller
        should include the note in the permission confirmation prompt.
        """
        matches = []
        for pattern in self._caution:
            m = pattern.search(command)
            if m:
                matches.append(m.group(0))
        if not matches:
            return False, ""
        note = "命令包含复合操作符（%s），执行前请确认安全性。" % "、".join(
            repr(t) for t in matches[:3]
        )
        return True, note


# Module-level default instance — share across all shell tools.
_DEFAULT_SANITIZER: Optional[CommandSanitizer] = None


def get_default_sanitizer() -> CommandSanitizer:
    global _DEFAULT_SANITIZER
    if _DEFAULT_SANITIZER is None:
        _DEFAULT_SANITIZER = CommandSanitizer()
    return _DEFAULT_SANITIZER
