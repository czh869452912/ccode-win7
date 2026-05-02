from __future__ import annotations

import fnmatch
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from embedagent.protocol import PermissionContextView
from embedagent.session import Action


def build_permission_explanation(
    tool_name: str,
    args_summary: str,
    risk_category: str,
    trigger_reason: str,
    rule_source: str,
    scope_text: str,
    memory_scope: str,
) -> str:
    return "\n".join(
        [
            "[请求] %s(%s)" % (tool_name, args_summary),
            "[风险] %s" % (risk_category,),
            "[原因] %s" % (trigger_reason,),
            "[规则] %s" % (rule_source,),
            "[范围] %s" % (scope_text,),
            "[记忆] %s" % (memory_scope,),
        ]
    )


READ_TOOLS = {
    "read_file",
    "list_dir",
    "glob_files",
    "grep_text",
    "list_recipes",
    "report_quality_v2",
    "task_status",
    "record_failing_evidence",
    "git_status",
    "git_diff",
    "git_log",
}
WORKSPACE_WRITE_TOOLS = {"edit_file", "write_file"}
SHELL_EXEC_TOOLS = {
    "run_command",
}
TOOLCHAIN_EXEC_TOOLS = {
    "run_recipe",
}
GIT_WRITE_TOOLS = set()
INTERACTION_TOOLS = {
    "ask_user",
    "propose_mode_switch",
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
    recipes: List[str] = field(default_factory=list)
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
            details = self._apply_rule_explanation(action, details, category, matched_rule)
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
        if category == "read" or action.name in INTERACTION_TOOLS:
            return PermissionDecision(outcome="allow", details=details)
        if category == "workspace_write" or category == "git_write":
            if self.auto_approve_writes:
                return PermissionDecision(outcome="allow", details=details)
            return PermissionDecision(
                outcome="ask",
                request=PermissionRequest(
                    tool_name=action.name,
                    category=category,
                    reason="该操作会修改工作区文件。",
                    details=details,
                ),
                details=details,
            )
        if category in ("shell_exec", "toolchain_exec"):
            if self.auto_approve_commands:
                return PermissionDecision(outcome="allow", details=details)
            return PermissionDecision(
                outcome="ask",
                request=PermissionRequest(
                    tool_name=action.name,
                    category=category,
                    reason=self._default_reason(category),
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
        except (OSError, json.JSONDecodeError, ValueError):
            return []
        items = payload.get("rules") if isinstance(payload, dict) else None
        return self._load_rules_from_items(items)

    def _load_rules_from_items(self, items: Any) -> List[PermissionRule]:
        if not isinstance(items, list):
            return []
        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            decision = str(item.get("decision") or "").strip().lower()
            if decision not in ("allow", "ask", "deny"):
                continue
            tool_names = self._list_of_strings(item.get("tool_names"))
            if not tool_names and str(item.get("tool") or "").strip():
                tool_names = [str(item.get("tool") or "").strip()]
            path_globs = self._list_of_strings(item.get("path_globs"))
            if not path_globs and str(item.get("path") or "").strip():
                path_globs = [str(item.get("path") or "").strip()]
            command_patterns = self._list_of_strings(item.get("command_patterns"))
            if not command_patterns and str(item.get("command_prefix") or "").strip():
                command_patterns = ["^%s" % re.escape(str(item.get("command_prefix") or "").strip())]
            result.append(
                PermissionRule(
                    decision=decision,
                    category=str(item.get("category") or "").strip().lower(),
                    tool_names=tool_names,
                    path_globs=path_globs,
                    cwd_globs=self._list_of_strings(item.get("cwd_globs")),
                    command_patterns=command_patterns,
                    recipes=self._list_of_strings(item.get("recipes") or item.get("recipe")),
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
            if rule.category and not self._category_matches(rule.category, category):
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
            if rule.recipes:
                recipe = str(details.get("recipe") or "")
                if not recipe or recipe not in rule.recipes:
                    continue
            matched = rule  # keep scanning; last match wins
        return matched

    def _category_matches(self, rule_category: str, actual_category: str) -> bool:
        normalized_rule = self._normalize_rule_category(rule_category)
        if normalized_rule == actual_category:
            return True
        if normalized_rule == "shell_or_toolchain":
            return actual_category in ("shell_exec", "toolchain_exec")
        return False

    def _normalize_rule_category(self, value: str) -> str:
        raw = str(value or "").strip().lower()
        aliases = {
            "write": "workspace_write",
            "command": "shell_or_toolchain",
            "safe": "read",
            "other": "other",
        }
        return aliases.get(raw, raw)

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
        if "recipe_id" in action.arguments:
            details["recipe"] = str(action.arguments.get("recipe_id") or "")
        details["explanation"] = self._render_explanation(
            action.name,
            details,
            category,
            self._default_reason(category),
            "default",
        )
        return details

    def _render_explanation(
        self,
        tool_name: str,
        details: Dict[str, Any],
        category: str,
        reason: str,
        rule_source: str,
    ) -> str:
        args_summary = []
        if details.get("path"):
            args_summary.append(str(details.get("path")))
        if details.get("recipe"):
            args_summary.append("recipe=%s" % details.get("recipe"))
        if details.get("command"):
            args_summary.append(str(details.get("command")))
        scope_text = str(details.get("path") or details.get("recipe") or details.get("command") or "session")
        return build_permission_explanation(
            tool_name=tool_name,
            args_summary=", ".join(args_summary) or "-",
            risk_category=category,
            trigger_reason=reason,
            rule_source=rule_source,
            scope_text=scope_text,
            memory_scope="session",
        )

    def _apply_rule_explanation(
        self,
        action: Action,
        details: Dict[str, Any],
        category: str,
        matched_rule: Optional[PermissionRule],
    ) -> Dict[str, Any]:
        payload = dict(details)
        if matched_rule is None:
            payload["rule_source"] = "default"
            payload["explanation"] = self._render_explanation(
                action.name,
                payload,
                category,
                self._default_reason(category),
                "default",
            )
            return payload
        source = "rules:%s" % (os.path.basename(self.rules_path) or "inline")
        payload["rule_source"] = source
        payload["explanation"] = self._render_explanation(
            action.name,
            payload,
            category,
            matched_rule.reason or self._default_reason(category),
            source,
        )
        return payload

    def _default_reason(self, category: str) -> str:
        if category == "workspace_write":
            return "该操作会修改工作区文件。"
        if category == "git_write":
            return "该操作会修改 Git 状态。"
        if category == "shell_exec":
            return "该操作会执行 shell 命令。"
        if category == "toolchain_exec":
            return "该操作会执行构建或验证工具链。"
        return "该操作需要确认。"

    def _category_for_action(self, action: Action) -> str:
        if action.name in WORKSPACE_WRITE_TOOLS:
            return "workspace_write"
        if action.name in GIT_WRITE_TOOLS:
            return "git_write"
        if action.name in SHELL_EXEC_TOOLS:
            return "shell_exec"
        if action.name in TOOLCHAIN_EXEC_TOOLS:
            return "toolchain_exec"
        if action.name in READ_TOOLS:
            return "read"
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

    def build_context_view(
        self,
        session_id: str = "",
        remembered_categories: Optional[List[str]] = None,
    ) -> PermissionContextView:
        categories = [
            "read",
            "workspace_write",
            "shell_exec",
            "toolchain_exec",
            "git_write",
        ]
        rules = []
        for rule in self.rules:
            rules.append(
                {
                    "decision": rule.decision,
                    "category": rule.category,
                    "tool_names": list(rule.tool_names),
                    "path_globs": list(rule.path_globs),
                    "cwd_globs": list(rule.cwd_globs),
                    "command_patterns": list(rule.command_patterns),
                    "recipes": list(rule.recipes),
                    "reason": rule.reason,
                }
            )
        return PermissionContextView(
            session_id=session_id,
            rules_path=self.rules_path.replace("\\", "/"),
            categories=categories,
            rules=rules,
            remembered_categories=sorted(list(set(remembered_categories or []))),
            auto_approve_all=self.auto_approve_all,
            auto_approve_writes=self.auto_approve_writes,
            auto_approve_commands=self.auto_approve_commands,
        )
