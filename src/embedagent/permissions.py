from __future__ import annotations

import fnmatch
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from embedagent.session import Action


WRITE_TOOLS = {"edit_file", "write_file"}
COMMAND_TOOLS = {
    "run_command",
    "compile_project",
    "run_tests",
    "run_clang_tidy",
    "run_clang_analyzer",
    "collect_coverage",
}
SAFE_TOOLS = {
    "read_file",
    "list_files",
    "search_text",
    "git_status",
    "git_diff",
    "git_log",
    "report_quality",
    "switch_mode",
    "ask_user",
}


@dataclass
class PermissionRequest:
    tool_name: str
    category: str
    reason: str
    details: Dict[str, Any]


@dataclass
class PermissionRule:
    decision: str
    category: str = ""
    tool_names: List[str] = field(default_factory=list)
    path_globs: List[str] = field(default_factory=list)
    cwd_globs: List[str] = field(default_factory=list)
    command_patterns: List[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class PermissionDecision:
    outcome: str
    request: Optional[PermissionRequest] = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class PermissionPolicy(object):
    def __init__(
        self,
        auto_approve_all: bool = False,
        auto_approve_writes: bool = False,
        auto_approve_commands: bool = False,
        workspace: str = "",
        rules_path: str = "",
    ) -> None:
        self.auto_approve_all = auto_approve_all
        self.auto_approve_writes = auto_approve_writes
        self.auto_approve_commands = auto_approve_commands
        self.workspace = os.path.realpath(workspace) if workspace else ""
        self.rules_path = self._resolve_rules_path(rules_path)
        self.rules = self._load_rules(self.rules_path)

    def evaluate(self, action: Action) -> PermissionDecision:
        category = self._category_for_action(action)
        details = self._build_details(action, category)
        matched_rule = self._match_rule(action, category, details)
        if matched_rule is not None:
            details = dict(details)
            details["rule_decision"] = matched_rule.decision
            details["rule_reason"] = matched_rule.reason
            if matched_rule.decision == "allow":
                return PermissionDecision(outcome="allow", details=details)
            if matched_rule.decision == "deny":
                return PermissionDecision(
                    outcome="deny",
                    error=matched_rule.reason or "权限规则拒绝该操作。",
                    details=details,
                )
            return PermissionDecision(
                outcome="ask",
                request=PermissionRequest(
                    tool_name=action.name,
                    category=category,
                    reason=matched_rule.reason or self._default_reason(category),
                    details=details,
                ),
                details=details,
            )
        if self.auto_approve_all:
            return PermissionDecision(outcome="allow", details=details)
        if action.name in SAFE_TOOLS:
            return PermissionDecision(outcome="allow", details=details)
        if action.name in WRITE_TOOLS:
            if self.auto_approve_writes:
                return PermissionDecision(outcome="allow", details=details)
            return PermissionDecision(
                outcome="ask",
                request=PermissionRequest(
                    tool_name=action.name,
                    category="write",
                    reason="该操作会修改工作区文件。",
                    details=details,
                ),
                details=details,
            )
        if action.name in COMMAND_TOOLS:
            if self.auto_approve_commands:
                return PermissionDecision(outcome="allow", details=details)
            return PermissionDecision(
                outcome="ask",
                request=PermissionRequest(
                    tool_name=action.name,
                    category="command",
                    reason="该操作会执行命令或工具链程序。",
                    details=details,
                ),
                details=details,
            )
        return PermissionDecision(outcome="allow", details=details)

    def build_request(self, action: Action) -> Optional[PermissionRequest]:
        decision = self.evaluate(action)
        return decision.request

    def _resolve_rules_path(self, rules_path: str) -> str:
        raw = (rules_path or "").strip()
        if raw:
            if not os.path.isabs(raw) and self.workspace:
                raw = os.path.join(self.workspace, raw)
            return os.path.realpath(raw)
        if not self.workspace:
            return ""
        return os.path.join(self.workspace, ".embedagent", "permission-rules.json")

    def _load_rules(self, path: str) -> List[PermissionRule]:
        if not path or not os.path.isfile(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return []
        items = payload.get("rules") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return []
        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            decision = str(item.get("decision") or "").strip().lower()
            if decision not in ("allow", "ask", "deny"):
                continue
            result.append(
                PermissionRule(
                    decision=decision,
                    category=str(item.get("category") or "").strip().lower(),
                    tool_names=self._list_of_strings(item.get("tool_names")),
                    path_globs=self._list_of_strings(item.get("path_globs")),
                    cwd_globs=self._list_of_strings(item.get("cwd_globs")),
                    command_patterns=self._list_of_strings(item.get("command_patterns")),
                    reason=str(item.get("reason") or "").strip(),
                )
            )
        return result

    def _match_rule(
        self,
        action: Action,
        category: str,
        details: Dict[str, Any],
    ) -> Optional[PermissionRule]:
        # Use last-match semantics: later rules in the list take precedence over
        # earlier ones.  This mirrors .gitignore / security-policy conventions
        # where project-level overrides (appended after global rules) win.
        matched = None
        for rule in self.rules:
            if rule.category and rule.category != category:
                continue
            if rule.tool_names and action.name not in rule.tool_names:
                continue
            if rule.path_globs:
                path = str(details.get("path") or "")
                if not path or not self._matches_globs(path, rule.path_globs):
                    continue
            if rule.cwd_globs:
                cwd = str(details.get("cwd") or "")
                if not cwd or not self._matches_globs(cwd, rule.cwd_globs):
                    continue
            if rule.command_patterns:
                command = str(details.get("command") or "")
                if not command or not self._matches_patterns(command, rule.command_patterns):
                    continue
            matched = rule  # keep scanning; last match wins
        return matched

    def _matches_globs(self, value: str, patterns: List[str]) -> bool:
        normalized = value.replace("\\", "/")
        for pattern in patterns:
            if fnmatch.fnmatch(normalized, pattern):
                return True
        return False

    def _matches_patterns(self, value: str, patterns: List[str]) -> bool:
        for pattern in patterns:
            try:
                if re.search(pattern, value):
                    return True
            except re.error:
                continue
        return False

    def _build_details(self, action: Action, category: str) -> Dict[str, Any]:
        details = {"category": category}
        if "path" in action.arguments:
            details["path"] = str(action.arguments.get("path") or "").replace("\\", "/")
        if "command" in action.arguments:
            details["command"] = str(action.arguments.get("command") or "")
        if "cwd" in action.arguments:
            details["cwd"] = str(action.arguments.get("cwd") or ".").replace("\\", "/")
        return details

    def _default_reason(self, category: str) -> str:
        if category == "write":
            return "该操作会修改工作区文件。"
        if category == "command":
            return "该操作会执行命令或工具链程序。"
        return "该操作需要确认。"

    def _category_for_action(self, action: Action) -> str:
        if action.name in WRITE_TOOLS:
            return "write"
        if action.name in COMMAND_TOOLS:
            return "command"
        if action.name in SAFE_TOOLS:
            return "safe"
        return "other"

    def _list_of_strings(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        result = []
        for item in value:
            text = str(item or "").strip()
            if text:
                result.append(text)
        return result
