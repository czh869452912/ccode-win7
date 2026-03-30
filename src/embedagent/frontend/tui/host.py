from __future__ import annotations

from embedagent.frontend.tui.state import CapabilityProfile


def detect_host() -> CapabilityProfile:
    if ("ConEmuPID" in __import__("os").environ) or (__import__("os").environ.get("ConEmuANSI", "").upper() == "ON"):
        return CapabilityProfile(host_mode="conemu", ascii_only=True, low_color=True, allow_mouse=False)
    return CapabilityProfile(host_mode="raw-console", ascii_only=True, low_color=True, allow_mouse=False)
