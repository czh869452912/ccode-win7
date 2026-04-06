from __future__ import annotations

from embedagent.permissions_v2.matcher import matches_rule


class PermissionPolicyV2(object):
    def __init__(self, rules=None):
        self.rules = list(rules or [])

    def evaluate(self, tool_name, path="", recipe="", command=""):
        for rule in self.rules:
            if matches_rule(rule, tool_name, path=path, recipe=recipe, command=command):
                return str(rule.decision or "ask")
        return "ask"
