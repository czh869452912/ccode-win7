from __future__ import annotations

import fnmatch


def matches_rule(rule, tool_name, path="", recipe="", command=""):
    if str(rule.tool or "").strip() and str(rule.tool) != str(tool_name):
        return False
    if str(rule.path or "").strip():
        if not str(path or ""):
            return False
        if not fnmatch.fnmatch(str(path).replace("\\", "/"), str(rule.path).replace("\\", "/")):
            return False
    if str(rule.recipe or "").strip() and str(rule.recipe) != str(recipe or ""):
        return False
    if str(rule.command_prefix or "").strip():
        if not str(command or "").startswith(str(rule.command_prefix)):
            return False
    return True
