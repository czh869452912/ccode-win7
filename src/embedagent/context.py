from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from embedagent.project_memory import ProjectMemoryStore
from embedagent.session import ContextAssemblyResult, Message, Observation, Session, Turn
from embedagent.workspace_intelligence import WorkspaceIntelligenceBroker


_MODE_RE = re.compile(r"当前模式：(\w+)")
_MODE_PROMPT_PREFIX = "你是 EmbedAgent 的受控模式原型。"

# Tool messages from these tools carry diagnostic/build results that are
# especially valuable for the LLM.  They are skipped when hard-trim needs
# to drop messages to fit within the token budget, so that a compile error
# on line 400 of the build log is not silently discarded before a trivial
# list_files result.
_HIGH_PRIORITY_TOOLS = frozenset({
    "compile_project",
    "run_tests",
    "run_clang_tidy",
    "run_clang_analyzer",
    "collect_coverage",
    "report_quality",
})


@dataclass
class ContextPolicy:
    mode_name: str
    max_context_tokens: int
    reserve_output_tokens: int
    reserve_reasoning_tokens: int
    max_recent_turns: int
    min_recent_turns: int
    max_summary_turns: int
    recent_message_chars: int
    recent_tool_chars: int
    summary_text_chars: int
    summary_tool_chars: int
    hard_message_chars: int
    hard_tool_chars: int
    project_memory_chars: int

    @property
    def max_input_tokens(self) -> int:
        budget = self.max_context_tokens - self.reserve_output_tokens - self.reserve_reasoning_tokens
        return budget if budget > 256 else 256


@dataclass
class ContextConfig:
    estimated_chars_per_token: float = 3.0
    default_max_context_tokens: int = 18000
    default_reserve_output_tokens: int = 2000
    default_reserve_reasoning_tokens: int = 1000
    default_max_recent_turns: int = 4
    default_min_recent_turns: int = 1
    default_max_summary_turns: int = 12
    default_recent_message_chars: int = 3000
    default_recent_tool_chars: int = 2500
    default_summary_text_chars: int = 240
    default_summary_tool_chars: int = 500
    default_hard_message_chars: int = 1200
    default_hard_tool_chars: int = 800
    default_project_memory_chars: int = 1600
    mode_overrides: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: {
            "ask": {"max_context_tokens": 12000, "reserve_output_tokens": 1600, "reserve_reasoning_tokens": 500, "max_recent_turns": 3, "max_summary_turns": 8},
            "orchestra": {"max_context_tokens": 14000, "reserve_output_tokens": 1800, "reserve_reasoning_tokens": 700, "max_recent_turns": 3, "max_summary_turns": 10},
            "spec": {"max_context_tokens": 14000, "reserve_output_tokens": 1800, "reserve_reasoning_tokens": 600, "max_recent_turns": 3, "max_summary_turns": 10},
            "code": {"max_context_tokens": 18000, "reserve_output_tokens": 2200, "reserve_reasoning_tokens": 1000, "max_recent_turns": 4, "max_summary_turns": 12},
            "test": {"max_context_tokens": 18000, "reserve_output_tokens": 2200, "reserve_reasoning_tokens": 1000, "max_recent_turns": 4, "max_summary_turns": 12},
            "verify": {"max_context_tokens": 18000, "reserve_output_tokens": 1800, "reserve_reasoning_tokens": 1200, "max_recent_turns": 3, "max_summary_turns": 10, "recent_tool_chars": 1800},
            "debug": {"max_context_tokens": 18000, "reserve_output_tokens": 2200, "reserve_reasoning_tokens": 1200, "max_recent_turns": 4, "max_summary_turns": 12},
            "compact": {"max_context_tokens": 9000, "reserve_output_tokens": 1200, "reserve_reasoning_tokens": 500, "max_recent_turns": 2, "max_summary_turns": 6, "recent_message_chars": 1600, "recent_tool_chars": 1200, "summary_text_chars": 160, "summary_tool_chars": 300, "hard_message_chars": 700, "hard_tool_chars": 450, "project_memory_chars": 700},
        }
    )


def make_context_config(app_config=None):
    # type: (Optional[Any]) -> ContextConfig
    """Build a ContextConfig from an AppConfig, falling back to defaults.

    Args:
        app_config: An embedagent.config.AppConfig instance, or None to use
                    all built-in defaults.
    """
    if app_config is None:
        return ContextConfig()
    kwargs = {}
    if getattr(app_config, "max_context_tokens", None) is not None:
        kwargs["default_max_context_tokens"] = int(app_config.max_context_tokens)
    if getattr(app_config, "reserve_output_tokens", None) is not None:
        kwargs["default_reserve_output_tokens"] = int(app_config.reserve_output_tokens)
    if getattr(app_config, "chars_per_token", None) is not None:
        kwargs["estimated_chars_per_token"] = float(app_config.chars_per_token)
    if getattr(app_config, "max_recent_turns", None) is not None:
        kwargs["default_max_recent_turns"] = int(app_config.max_recent_turns)
    return ContextConfig(**kwargs)


@dataclass
class BudgetEstimate:
    mode_name: str
    max_context_tokens: int
    reserve_output_tokens: int
    reserve_reasoning_tokens: int
    max_input_tokens: int
    input_tokens: int
    remaining_input_tokens: int
    over_budget: bool


@dataclass
class ContextStats:
    mode_name: str
    total_session_messages: int
    selected_messages: int
    total_turns: int
    recent_turns: int
    summarized_turns: int
    summarized_observations: int
    reduced_tool_messages: int
    characters_before: int
    characters_after: int
    approx_tokens_before: int
    approx_tokens_after: int
    dropped_messages: int
    recent_window_shrinks: int
    hard_trimmed: bool
    summary_message_included: bool
    project_memory_included: bool


@dataclass
class ContextBuildResult:
    messages: List[Dict[str, Any]]
    used_chars: int
    approx_tokens: int
    compacted: bool
    summarized_turns: int
    recent_turns: int
    policy: ContextPolicy
    budget: BudgetEstimate
    stats: ContextStats
    summary_message: str = ""
    intelligence_sections: List[Dict[str, Any]] = field(default_factory=list)
    analysis: Dict[str, Any] = field(default_factory=dict)
    replacements: List[Dict[str, Any]] = field(default_factory=list)
    pipeline_steps: List[str] = field(default_factory=list)


class TokenEstimator(object):
    def __init__(self, chars_per_token: float = 3.0) -> None:
        self.chars_per_token = chars_per_token if chars_per_token > 0 else 1.0

    def estimate_text(self, text: str) -> int:
        return int(math.ceil(float(len(text or "")) / self.chars_per_token))

    def estimate_messages(self, messages: List[Dict[str, Any]]) -> int:
        return sum(self.estimate_text(json.dumps(message, ensure_ascii=False)) for message in messages)

class ReducerRegistry(object):
    def __init__(self) -> None:
        self._reducers = {
            "read_file": self._reduce_file,
            "list_files": self._reduce_list,
            "search_text": self._reduce_search,
            "write_file": self._reduce_write,
            "edit_file": self._reduce_edit,
            "run_command": self._reduce_command,
            "git_status": self._reduce_git_status,
            "git_diff": self._reduce_git_diff,
            "git_log": self._reduce_git_log,
            "compile_project": self._reduce_diagnostics_tool,
            "run_tests": self._reduce_tests,
            "run_clang_tidy": self._reduce_diagnostics_tool,
            "run_clang_analyzer": self._reduce_diagnostics_tool,
            "collect_coverage": self._reduce_coverage,
            "report_quality": self._reduce_quality,
            "switch_mode": self._reduce_switch_mode,
            "ask_user": self._reduce_ask_user,
            "manage_todos": self._reduce_todos,
        }

    def reduce_tool_message(self, tool_name: str, payload: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> str:
        compacted = {
            "success": payload.get("success"),
            "error": payload.get("error"),
            "data": self.reduce_tool_data(tool_name, payload.get("data"), detailed, policy),
        }
        raw = json.dumps(compacted, ensure_ascii=False, sort_keys=True)
        limit = policy.recent_tool_chars if detailed else policy.summary_tool_chars
        return _truncate_text(raw, limit)

    def reduce_tool_data(self, tool_name: str, data: Any, detailed: bool, policy: ContextPolicy) -> Any:
        if not isinstance(data, dict):
            return _truncate_text(str(data), self._text_limit(detailed, policy)) if isinstance(data, str) else data
        reducer = self._reducers.get(tool_name, self._reduce_generic)
        return reducer(data, detailed, policy)

    def summarize_observation(self, observation: Observation, detailed: bool, policy: ContextPolicy) -> str:
        reduced = self.reduce_tool_data(observation.tool_name, observation.data, detailed, policy)
        parts = [observation.tool_name, "success" if observation.success else "failed"]
        if observation.error:
            parts.append(_single_line(_truncate_text(observation.error, 80)))
        if isinstance(reduced, dict):
            for key, label in (("path", "path"), ("match_count", "matches"), ("exit_code", "exit"), ("error_count", "errors"), ("warning_count", "warnings"), ("diagnostic_count", "diagnostics"), ("to_mode", "to"), ("passed", "passed")):
                if reduced.get(key) is not None:
                    parts.append("%s=%s" % (label, reduced[key]))
            if reduced.get("test_summary"):
                summary = reduced["test_summary"]
                parts.append("tests=%s/%s failed=%s" % (summary.get("passed"), summary.get("total"), summary.get("failed")))
            if reduced.get("coverage_summary") and reduced["coverage_summary"].get("line_coverage") is not None:
                parts.append("line=%.2f%%" % reduced["coverage_summary"]["line_coverage"])
        return ", ".join(parts)

    def _reduce_file(self, data: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> Dict[str, Any]:
        result = self._copy(data, "path", "encoding", "char_count", "line_count", "truncated", "content_artifact_ref")
        if isinstance(data.get("content"), str):
            result["content_preview"] = _truncate_text(data["content"], min(self._text_limit(detailed, policy), 1200 if detailed else 320))
        return result

    def _reduce_list(self, data: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> Dict[str, Any]:
        files = data.get("files") if isinstance(data.get("files"), list) else []
        result = self._copy(data, "path", "pattern", "count", "truncated", "files_artifact_ref", "files_item_count")
        result["files"] = self._simple_list(files, 12 if detailed else 6)
        if files:
            counts = {}
            for item in files:
                path = str(item)
                ext = path.rsplit(".", 1)[-1].lower() if "." in path else "(no_ext)"
                counts[ext] = counts.get(ext, 0) + 1
            ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
            result["extensions"] = [{"ext": ext, "count": count} for ext, count in ranked[: (6 if detailed else 4)]]
        return result

    def _reduce_search(self, data: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> Dict[str, Any]:
        result = self._copy(data, "query", "path", "match_count", "truncated", "matches_artifact_ref", "matches_item_count")
        matches = []
        for item in (data.get("matches") or [])[: (5 if detailed else 3)]:
            if isinstance(item, dict):
                reduced = self._copy(item, "path", "line")
                if isinstance(item.get("text"), str):
                    reduced["text"] = _truncate_text(item["text"], 200 if detailed else 100)
                matches.append(reduced)
        result["matches"] = matches
        return result

    def _reduce_edit(self, data: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> Dict[str, Any]:
        return self._copy(data, "path", "encoding", "replaced", "line_count")

    def _reduce_write(self, data: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> Dict[str, Any]:
        return self._copy(data, "path", "encoding", "created", "overwritten", "char_count", "line_count")

    def _reduce_command(self, data: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> Dict[str, Any]:
        result = self._copy(data, "command", "cwd", "exit_code", "duration_ms", "timed_out", "toolchain_root", "stdout_truncated", "stderr_truncated", "stdout_artifact_ref", "stderr_artifact_ref", "stdout_char_count", "stderr_char_count")
        preview = min(self._text_limit(detailed, policy), 1200 if detailed else 320)
        if isinstance(data.get("stdout"), str):
            result["stdout_preview"] = _truncate_text(data["stdout"], preview)
        if isinstance(data.get("stderr"), str):
            result["stderr_preview"] = _truncate_text(data["stderr"], preview)
        return result

    def _reduce_diagnostics_tool(self, data: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> Dict[str, Any]:
        result = self._reduce_command(data, detailed, policy)
        result.update(self._copy(data, "error_count", "warning_count", "note_count", "diagnostic_count", "diagnostics_artifact_ref", "diagnostics_item_count"))
        result["diagnostics"] = self._diagnostics(data.get("diagnostics") or [], detailed)
        return result

    def _reduce_tests(self, data: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> Dict[str, Any]:
        result = self._reduce_diagnostics_tool(data, detailed, policy)
        if isinstance(data.get("test_summary"), dict):
            summary = self._copy(data["test_summary"], "total", "passed", "failed", "skipped")
            summary["failures"] = self._simple_list(data["test_summary"].get("failures") or [], 5 if detailed else 3)
            result["test_summary"] = summary
        return result

    def _reduce_coverage(self, data: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> Dict[str, Any]:
        result = self._reduce_command(data, detailed, policy)
        if isinstance(data.get("coverage_summary"), dict):
            result["coverage_summary"] = self._copy(data["coverage_summary"], "line_coverage", "region_coverage", "function_coverage", "lines_covered", "lines_total", "functions_covered", "functions_total", "regions_covered", "regions_total")
        return result

    def _reduce_quality(self, data: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> Dict[str, Any]:
        result = self._copy(data, "passed", "error_count", "warning_count", "test_failures", "line_coverage", "min_line_coverage")
        result["reasons"] = self._simple_list(data.get("reasons") or [], 6 if detailed else 3)
        return result

    def _reduce_git_status(self, data: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> Dict[str, Any]:
        result = self._reduce_command(data, detailed, policy)
        result.update(self._copy(data, "path", "branch", "entries_artifact_ref", "entries_item_count"))
        entries = []
        for item in (data.get("entries") or [])[: (12 if detailed else 6)]:
            if isinstance(item, dict):
                entries.append(self._copy(item, "status", "path"))
        result["entries"] = entries
        return result

    def _reduce_git_diff(self, data: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> Dict[str, Any]:
        result = self._reduce_command(data, detailed, policy)
        result.update(self._copy(data, "path", "scope", "file_count", "line_count", "diff_artifact_ref", "diff_char_count"))
        if isinstance(data.get("diff"), str):
            result["diff_preview"] = _truncate_text(data["diff"], min(self._text_limit(detailed, policy), 1200 if detailed else 260))
        return result

    def _reduce_git_log(self, data: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> Dict[str, Any]:
        result = self._reduce_command(data, detailed, policy)
        result.update(self._copy(data, "path", "limit", "entries_artifact_ref", "entries_item_count"))
        entries = []
        for item in (data.get("entries") or [])[: (8 if detailed else 4)]:
            if isinstance(item, dict):
                reduced = self._copy(item, "author", "date", "subject")
                if item.get("commit"):
                    reduced["commit"] = str(item["commit"])[:12]
                if isinstance(reduced.get("subject"), str):
                    reduced["subject"] = _truncate_text(reduced["subject"], 120)
                entries.append(reduced)
        result["entries"] = entries
        return result

    def _reduce_switch_mode(self, data: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> Dict[str, Any]:
        result = self._copy(data, "from_mode", "to_mode", "reason")
        result["allowed_tools"] = self._simple_list(data.get("allowed_tools") or [], 6 if detailed else 4)
        return result

    def _reduce_ask_user(self, data: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> Dict[str, Any]:
        result = self._copy(
            data,
            "question",
            "answer",
            "selected_index",
            "selected_option_text",
            "selected_mode",
            "mode_changed",
        )
        options = []
        for item in (data.get("options") or [])[: (4 if detailed else 2)]:
            if isinstance(item, dict):
                options.append(self._copy(item, "index", "text", "mode"))
        if options:
            result["options"] = options
        return result

    def _reduce_todos(self, data: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> Dict[str, Any]:
        result = self._copy(data, "action", "count", "id", "content", "removed_id", "remaining")
        todos = data.get("todos")
        if isinstance(todos, list):
            limit = 12 if detailed else 6
            result["todos"] = self._simple_list(todos, limit)
        return result

    def _reduce_generic(self, data: Dict[str, Any], detailed: bool, policy: ContextPolicy) -> Dict[str, Any]:
        result = self._copy(data, "path", "query", "count", "match_count", "command", "cwd", "exit_code", "duration_ms", "timed_out", "error_count", "warning_count", "note_count", "diagnostic_count", "branch", "scope", "file_count", "line_count", "replaced", "created", "overwritten", "toolchain_root", "passed", "test_failures", "line_coverage", "min_line_coverage", "truncated", "encoding", "char_count", "limit", "from_mode", "to_mode", "reason", "question", "answer", "selected_index", "selected_option_text", "selected_mode", "mode_changed", "error_kind", "retryable", "blocked_by", "suggested_next_step", "content_artifact_ref", "content_char_count", "stdout_artifact_ref", "stderr_artifact_ref", "stdout_char_count", "stderr_char_count", "diff_artifact_ref", "diff_char_count", "files_artifact_ref", "files_item_count", "matches_artifact_ref", "matches_item_count", "entries_artifact_ref", "entries_item_count", "diagnostics_artifact_ref", "diagnostics_item_count")
        for key in ("entries", "matches", "files", "reasons"):
            if isinstance(data.get(key), list):
                result[key] = self._simple_list(data[key], 8 if detailed else 4)
        if isinstance(data.get("diagnostics"), list):
            result["diagnostics"] = self._diagnostics(data["diagnostics"], detailed)
        if isinstance(data.get("test_summary"), dict):
            result["test_summary"] = self._copy(data["test_summary"], "total", "passed", "failed", "skipped")
        if isinstance(data.get("coverage_summary"), dict):
            result["coverage_summary"] = self._copy(data["coverage_summary"], "line_coverage", "region_coverage", "function_coverage")
        preview = min(self._text_limit(detailed, policy), 1200 if detailed else 300)
        for source, target in (("content", "content_preview"), ("stdout", "stdout_preview"), ("stderr", "stderr_preview"), ("diff", "diff_preview")):
            if isinstance(data.get(source), str):
                result[target] = _truncate_text(data[source], preview)
        return result

    def _diagnostics(self, items: List[Any], detailed: bool) -> List[Dict[str, Any]]:
        diagnostics = []
        for item in items[: (6 if detailed else 3)]:
            if isinstance(item, dict):
                reduced = self._copy(item, "file", "line", "column", "level")
                if isinstance(item.get("message"), str):
                    reduced["message"] = _truncate_text(item["message"], 220 if detailed else 120)
                diagnostics.append(reduced)
        return diagnostics

    def _simple_list(self, items: List[Any], limit: int) -> List[Any]:
        result = []
        for item in items[:limit]:
            if isinstance(item, dict):
                reduced = {}
                for key, value in item.items():
                    reduced[key] = _truncate_text(value, 120) if isinstance(value, str) else value
                result.append(reduced)
            elif isinstance(item, str):
                result.append(_truncate_text(item, 120))
            else:
                result.append(item)
        return result

    def _copy(self, data: Dict[str, Any], *keys: str) -> Dict[str, Any]:
        return dict((key, data[key]) for key in keys if key in data)

    def _text_limit(self, detailed: bool, policy: ContextPolicy) -> int:
        return policy.recent_tool_chars if detailed else policy.summary_tool_chars

class ContextManager(object):
    def __init__(self, config: Optional[ContextConfig] = None, reducers: Optional[ReducerRegistry] = None, project_memory: Optional[ProjectMemoryStore] = None, token_estimator: Optional[TokenEstimator] = None) -> None:
        self.config = config or ContextConfig()
        self.reducers = reducers or ReducerRegistry()
        self.project_memory = project_memory
        self.token_estimator = token_estimator or TokenEstimator(self.config.estimated_chars_per_token)

    def build_messages(self, session: Session, mode_name: Optional[str] = None, tools: Optional[Any] = None, workflow_state: str = "chat", intelligence_broker: Optional[WorkspaceIntelligenceBroker] = None, force_compact: bool = False) -> ContextBuildResult:
        resolved_mode = mode_name or self._detect_mode_name(session) or "code"
        policy = self._policy_for_mode("compact" if force_compact else resolved_mode)
        boundary = session.latest_compact_boundary() if hasattr(session, "latest_compact_boundary") else None
        visible_turns = session.turns[int(boundary.compacted_turn_count):] if boundary is not None else session.turns
        raw_messages = [message.to_api_dict() for message in session.messages]
        chars_before = self._measure_messages(raw_messages)
        tokens_before = self._estimate_tokens(chars_before)
        intelligence_message = ""
        intelligence_sections = []
        if intelligence_broker is not None and tools is not None:
            intelligence_message = intelligence_broker.render_system_message(session, resolved_mode, tools, self.project_memory, limit=3, char_limit=policy.project_memory_chars)
            intelligence_sections = [
                {"title": "workspace_intelligence", "content": intelligence_message}
            ] if intelligence_message else []
        if not visible_turns:
            messages = [self._compact_message(message, policy) for message in session.messages]
            if intelligence_message:
                messages.insert(0, {"role": "system", "content": intelligence_message})
            used_chars = self._measure_messages(messages)
            budget = self._budget_for_chars(policy, used_chars)
            stats = ContextStats(
                mode_name=resolved_mode,
                total_session_messages=len(session.messages),
                selected_messages=len(messages),
                total_turns=0,
                recent_turns=0,
                summarized_turns=0,
                summarized_observations=0,
                reduced_tool_messages=0,
                characters_before=chars_before,
                characters_after=used_chars,
                approx_tokens_before=tokens_before,
                approx_tokens_after=budget.input_tokens,
                dropped_messages=max(0, len(session.messages) - len(messages)),
                recent_window_shrinks=0,
                hard_trimmed=False,
                summary_message_included=bool(boundary),
                project_memory_included=bool(intelligence_message),
            )
            pipeline_steps = ["working_set", "workspace_intelligence", "summary/compact", "prompt_render"]
            if force_compact:
                pipeline_steps.insert(0, "reactive_compact_retry")
            return ContextBuildResult(messages, used_chars, budget.input_tokens, used_chars < chars_before, 0, 0, policy, budget, stats, summary_message=boundary.summary_text if boundary is not None else "", intelligence_sections=intelligence_sections, analysis=self._analyze_context(session), replacements=[], pipeline_steps=pipeline_steps)
        recent_turns = min(policy.max_recent_turns, len(visible_turns))
        best = None  # type: Optional[ContextBuildResult]
        shrinks = 0
        while recent_turns >= policy.min_recent_turns:
            candidate = self._build_candidate(session, visible_turns, boundary.summary_text if boundary is not None else "", policy, recent_turns, chars_before, tokens_before, shrinks, intelligence_message, intelligence_sections)
            best = candidate
            if not candidate.budget.over_budget:
                if force_compact and "reactive_compact_retry" not in candidate.pipeline_steps:
                    candidate.pipeline_steps.insert(0, "reactive_compact_retry")
                return candidate
            recent_turns -= 1
            shrinks += 1
        assert best is not None
        best.messages, dropped_messages = self._hard_trim(best.messages, policy)
        best.used_chars = self._measure_messages(best.messages)
        best.approx_tokens = self._estimate_tokens(best.used_chars)
        best.budget = self._budget_for_chars(policy, best.used_chars)
        best.compacted = True
        best.stats.characters_after = best.used_chars
        best.stats.approx_tokens_after = best.approx_tokens
        best.stats.selected_messages = len(best.messages)
        best.stats.dropped_messages += dropped_messages
        best.stats.hard_trimmed = True
        if force_compact and "reactive_compact_retry" not in best.pipeline_steps:
            best.pipeline_steps.insert(0, "reactive_compact_retry")
        return best

    def _build_candidate(self, session: Session, visible_turns: List[Turn], boundary_summary: str, policy: ContextPolicy, recent_turns: int, chars_before: int, tokens_before: int, shrinks: int, intelligence_message: str, intelligence_sections: List[Dict[str, Any]]) -> ContextBuildResult:
        latest_system = self._latest_system_message(session)
        auxiliary_system_messages = self._auxiliary_system_messages(session, latest_system, policy)
        old_turns = visible_turns[:-recent_turns] if recent_turns < len(visible_turns) else []
        summary_message, summarized_observations, summary_text = self._build_summary_message(old_turns, policy, base_summary_text=boundary_summary)
        project_memory_message = self._build_project_memory_message(policy)
        recent_messages, reduced_tool_messages, replacements = self._build_recent_messages(session, visible_turns, recent_turns, policy)
        messages = []
        if latest_system is not None:
            messages.append(self._compact_system_message(latest_system, policy))
        messages.extend(auxiliary_system_messages)
        if intelligence_message:
            messages.append({"role": "system", "content": intelligence_message})
        if project_memory_message is not None:
            messages.append(project_memory_message)
        if summary_message is not None:
            messages.append(summary_message)
        messages.extend(recent_messages)
        used_chars = self._measure_messages(messages)
        budget = self._budget_for_chars(policy, used_chars)
        stats = ContextStats(
            mode_name=policy.mode_name,
            total_session_messages=len(session.messages),
            selected_messages=len(messages),
            total_turns=len(session.turns),
            recent_turns=recent_turns,
            summarized_turns=len(old_turns),
            summarized_observations=summarized_observations,
            reduced_tool_messages=reduced_tool_messages,
            characters_before=chars_before,
            characters_after=used_chars,
            approx_tokens_before=tokens_before,
            approx_tokens_after=budget.input_tokens,
            dropped_messages=max(0, len(session.messages) - len(messages)),
            recent_window_shrinks=shrinks,
            hard_trimmed=False,
            summary_message_included=summary_message is not None,
            project_memory_included=project_memory_message is not None or bool(intelligence_message),
        )
        compacted = bool(old_turns) or bool(reduced_tool_messages) or (used_chars < chars_before)
        return ContextBuildResult(messages, used_chars, budget.input_tokens, compacted, len(old_turns), recent_turns, policy, budget, stats, summary_message=summary_text, intelligence_sections=intelligence_sections, analysis=self._analyze_context(session), replacements=replacements, pipeline_steps=["working_set", "workspace_intelligence", "tool_result_budget_replacement", "duplicate_suppression", "activity_folding", "summary/compact", "prompt_render"])

    def _policy_for_mode(self, mode_name: str) -> ContextPolicy:
        values = {
            "max_context_tokens": self.config.default_max_context_tokens,
            "reserve_output_tokens": self.config.default_reserve_output_tokens,
            "reserve_reasoning_tokens": self.config.default_reserve_reasoning_tokens,
            "max_recent_turns": self.config.default_max_recent_turns,
            "min_recent_turns": self.config.default_min_recent_turns,
            "max_summary_turns": self.config.default_max_summary_turns,
            "recent_message_chars": self.config.default_recent_message_chars,
            "recent_tool_chars": self.config.default_recent_tool_chars,
            "summary_text_chars": self.config.default_summary_text_chars,
            "summary_tool_chars": self.config.default_summary_tool_chars,
            "hard_message_chars": self.config.default_hard_message_chars,
            "hard_tool_chars": self.config.default_hard_tool_chars,
            "project_memory_chars": self.config.default_project_memory_chars,
        }
        values.update(self.config.mode_overrides.get(mode_name) or {})
        return ContextPolicy(mode_name=mode_name, **values)

    def _latest_system_message(self, session: Session) -> Optional[Message]:
        for message in reversed(session.messages):
            if self._is_mode_system_message(message):
                return message
        for message in reversed(session.messages):
            if message.role == "system":
                return message
        return None

    def _detect_mode_name(self, session: Session) -> Optional[str]:
        latest_system = self._latest_system_message(session)
        if latest_system is None:
            return None
        match = _MODE_RE.search(latest_system.content)
        return match.group(1) if match else None

    def _is_mode_system_message(self, message: Message) -> bool:
        if message.role != "system":
            return False
        if _MODE_PROMPT_PREFIX not in message.content:
            return False
        return bool(_MODE_RE.search(message.content))

    def _auxiliary_system_messages(
        self,
        session: Session,
        latest_system: Optional[Message],
        policy: ContextPolicy,
    ) -> List[Dict[str, Any]]:
        result = []
        for message in session.messages:
            if message.role != "system":
                continue
            if latest_system is not None and message is latest_system:
                continue
            if self._is_mode_system_message(message):
                continue
            result.append(self._compact_system_message(message, policy))
        return result[-2:]

    def _build_project_memory_message(self, policy: ContextPolicy) -> Optional[Dict[str, Any]]:
        if self.project_memory is None:
            return None
        content = self.project_memory.build_system_message(policy.mode_name, policy.project_memory_chars)
        if not content:
            return None
        return {"role": "system", "content": content}

    def _build_summary_message(self, turns: List[Turn], policy: ContextPolicy, base_summary_text: str = "") -> Tuple[Optional[Dict[str, Any]], int, str]:
        if not turns and not base_summary_text:
            return None, 0, ""
        visible_turns = turns[-policy.max_summary_turns :]
        omitted = len(turns) - len(visible_turns)
        summarized_observations = 0
        lines = ["以下是更早会话的压缩摘要，仅供上下文参考；若与最近消息冲突，以最近消息和最新系统提示为准。"]
        if base_summary_text:
            lines.append("先前 compact 摘要：%s" % _truncate_text(base_summary_text, policy.summary_text_chars * 2))
        if omitted > 0:
            lines.append("更早还有 %s 个 turn 已进一步折叠。" % omitted)
        for index, turn in enumerate(visible_turns, start=1):
            lines.append("%s. 用户：%s" % (index, _truncate_text(turn.user_message, policy.summary_text_chars)))
            if turn.actions:
                lines.append("   动作：%s" % ", ".join([action.name for action in turn.actions[:6]]))
            if turn.observations:
                visible = [self.reducers.summarize_observation(item, False, policy) for item in turn.observations[:3]]
                visible = [item for item in visible if item]
                summarized_observations += len(turn.observations)
                if visible:
                    lines.append("   观测：%s" % " | ".join(visible))
            if turn.assistant_message:
                lines.append("   结果：%s" % _truncate_text(turn.assistant_message, policy.summary_text_chars))
        limit = max(400, policy.max_summary_turns * policy.summary_text_chars)
        summary_text = _truncate_text("\n".join(lines), limit)
        return {"role": "system", "content": summary_text}, summarized_observations, summary_text

    def _build_recent_messages(self, session: Session, visible_turns: List[Turn], recent_turns: int, policy: ContextPolicy) -> Tuple[List[Dict[str, Any]], int, List[Dict[str, Any]]]:
        turns = visible_turns[-recent_turns:]
        if not turns:
            return [], 0, []
        start_index = turns[0].message_start_index
        end_index = turns[-1].message_end_index
        result = []
        reduced_tool_messages = 0
        replacements = []
        seen_reads = set()
        seen_searches = set()
        pending_activity = {"read": 0, "search": 0, "list": 0}
        expected_tool_call_ids = set()
        replacement_index = {}
        for item in getattr(session, "content_replacements", []) or []:
            message_id = str(item.get("message_id") or "")
            if not message_id:
                continue
            texts = []
            if isinstance(item.get("replacements"), list):
                for replacement in item.get("replacements") or []:
                    text = str((replacement or {}).get("replacement_text") or "").strip()
                    if text:
                        texts.append(text)
            else:
                text = str(item.get("replacement_text") or "").strip()
                if text:
                    texts.append(text)
            if texts:
                replacement_index[message_id] = texts

        def flush_activity() -> None:
            parts = []
            if pending_activity["search"]:
                parts.append("searched %s patterns" % pending_activity["search"])
            if pending_activity["read"]:
                parts.append("read %s files" % pending_activity["read"])
            if pending_activity["list"]:
                parts.append("listed %s directories" % pending_activity["list"])
            if parts:
                result.append({"role": "system", "content": "Recent activity: " + ", ".join(parts)})
            pending_activity["read"] = 0
            pending_activity["search"] = 0
            pending_activity["list"] = 0

        for message in session.messages[start_index : end_index + 1]:
            if message.role == "system":
                continue
            if message.role == "assistant":
                expected_tool_call_ids = set(
                    str(action.call_id or "").strip()
                    for action in (message.action_calls or [])
                    if str(action.call_id or "").strip()
                )
            elif message.role != "tool":
                expected_tool_call_ids = set()
            if message.role == "tool":
                call_id = str(message.tool_call_id or "").strip()
                if call_id and call_id in expected_tool_call_ids:
                    flush_activity()
                    result.append(self._compact_message(message, policy))
                    expected_tool_call_ids.discard(call_id)
                    continue
                restored_replacement = replacement_index.get(message.message_id)
                if restored_replacement is not None:
                    reduced_tool_messages += 1
                    for replacement_text in restored_replacement:
                        replacements.append(
                            {
                                "tool_name": str(message.name or ""),
                                "message_id": message.message_id,
                                "tool_call_id": message.tool_call_id,
                                "replacement_text": replacement_text,
                            }
                        )
                        result.append({"role": "system", "content": replacement_text})
                    continue
                reduced_tool_messages += 1
                replacement = self._compact_tool_message_with_replacements(message, policy, seen_reads, seen_searches)
                if replacement is not None:
                    replacements.append(replacement["replacement"])
                    pending_activity[replacement["activity_kind"]] = pending_activity.get(replacement["activity_kind"], 0) + 1
                    if replacement["message"] is not None:
                        result.append(replacement["message"])
                    continue
                flush_activity()
            else:
                flush_activity()
            result.append(self._compact_message(message, policy))
        flush_activity()
        return result, reduced_tool_messages, replacements

    def _compact_system_message(self, message: Message, policy: ContextPolicy) -> Dict[str, Any]:
        return {"role": "system", "content": _truncate_text(message.content, policy.recent_message_chars)}

    def _compact_message(self, message: Message, policy: ContextPolicy) -> Dict[str, Any]:
        payload = {"role": message.role}
        if message.name:
            payload["name"] = message.name
        if message.tool_call_id:
            payload["tool_call_id"] = message.tool_call_id
        if message.action_calls:
            payload["tool_calls"] = [action.to_api_dict() for action in message.action_calls]
        if message.reasoning_content:
            payload["reasoning_content"] = _truncate_text(message.reasoning_content, policy.recent_message_chars)
        if message.role == "tool":
            try:
                parsed = json.loads(message.content)
            except ValueError:
                payload["content"] = _truncate_text(message.content, policy.recent_tool_chars)
            else:
                parsed = parsed if isinstance(parsed, dict) else {"data": parsed}
                payload["content"] = self.reducers.reduce_tool_message(message.name or "", parsed, True, policy)
        else:
            payload["content"] = _truncate_text(message.content, policy.recent_message_chars)
        return payload

    def _compact_tool_message_with_replacements(
        self,
        message: Message,
        policy: ContextPolicy,
        seen_reads: set,
        seen_searches: set,
    ) -> Optional[Dict[str, Any]]:
        try:
            parsed = json.loads(message.content)
        except ValueError:
            return None
        parsed = parsed if isinstance(parsed, dict) else {"data": parsed}
        data = parsed.get("data") if isinstance(parsed.get("data"), dict) else {}
        tool_name = str(message.name or "")
        replacement = {
            "tool_name": tool_name,
            "message_id": message.message_id,
            "tool_call_id": message.tool_call_id,
            "artifact_refs": [],
            "duplicate": False,
            "replacement_text": "",
        }
        for key, value in data.items():
            if key.endswith("_artifact_ref") and value:
                replacement["artifact_refs"].append(value)
        if tool_name == "read_file":
            path = str(data.get("path") or "")
            if path:
                if path in seen_reads:
                    replacement["duplicate"] = True
                    return {
                        "activity_kind": "read",
                        "replacement": replacement,
                        "message": {"role": "system", "content": "Duplicate read suppressed for `%s`." % path},
                    }
                seen_reads.add(path)
                if replacement["artifact_refs"]:
                    replacement["replacement_text"] = "Tool result replaced: read_file %s -> %s" % (
                        path,
                        replacement["artifact_refs"][0],
                    )
                    return {
                        "activity_kind": "read",
                        "replacement": replacement,
                        "message": {"role": "system", "content": replacement["replacement_text"]},
                    }
        if tool_name == "search_text":
            key = "%s|%s" % (str(data.get("path") or ""), str(data.get("query") or ""))
            if key.strip("|"):
                if key in seen_searches:
                    replacement["duplicate"] = True
                    return {
                        "activity_kind": "search",
                        "replacement": replacement,
                        "message": {"role": "system", "content": "Duplicate search suppressed for `%s`." % key},
                    }
                seen_searches.add(key)
                if replacement["artifact_refs"]:
                    replacement["replacement_text"] = "Tool result replaced: search_text %s -> %s" % (
                        key,
                        replacement["artifact_refs"][0],
                    )
                    return {
                        "activity_kind": "search",
                        "replacement": replacement,
                        "message": {"role": "system", "content": replacement["replacement_text"]},
                    }
        if tool_name == "list_files" and replacement["artifact_refs"]:
            replacement["replacement_text"] = "Tool result replaced: list_files %s -> %s" % (
                str(data.get("path") or "."),
                replacement["artifact_refs"][0],
            )
            return {
                "activity_kind": "list",
                "replacement": replacement,
                "message": {"role": "system", "content": replacement["replacement_text"]},
            }
        return None

    def _budget_for_chars(self, policy: ContextPolicy, used_chars: int) -> BudgetEstimate:
        input_tokens = self._estimate_tokens(used_chars)
        remaining = policy.max_input_tokens - input_tokens
        return BudgetEstimate(policy.mode_name, policy.max_context_tokens, policy.reserve_output_tokens, policy.reserve_reasoning_tokens, policy.max_input_tokens, input_tokens, remaining, input_tokens > policy.max_input_tokens)

    def _estimate_tokens(self, used_chars: int) -> int:
        ratio = self.token_estimator.chars_per_token or 1.0
        return int(math.ceil(float(max(0, used_chars)) / ratio))

    def _measure_messages(self, messages: List[Dict[str, Any]]) -> int:
        return sum(len(json.dumps(message, ensure_ascii=False)) for message in messages)

    def _hard_trim(self, messages: List[Dict[str, Any]], policy: ContextPolicy) -> Tuple[List[Dict[str, Any]], int]:
        trimmed = []
        for message in messages:
            clone = dict(message)
            limit = policy.hard_tool_chars if clone.get("role") == "tool" else policy.hard_message_chars
            clone["content"] = _truncate_text(str(clone.get("content") or ""), limit)
            if clone.get("reasoning_content"):
                clone["reasoning_content"] = _truncate_text(str(clone["reasoning_content"]), policy.hard_message_chars)
            trimmed.append(clone)
        dropped_messages = 0
        while self._budget_for_chars(policy, self._measure_messages(trimmed)).over_budget and len(trimmed) > 3:
            drop_index = self._oldest_non_system_index(trimmed)
            if drop_index is None:
                break
            drop_indices = self._trim_chunk_indices(trimmed, drop_index)
            if not drop_indices:
                break
            trimmed = [
                message
                for index, message in enumerate(trimmed)
                if index not in drop_indices
            ]
            dropped_messages += len(drop_indices)
        return trimmed, dropped_messages

    def _oldest_non_system_index(self, messages: List[Dict[str, Any]]) -> Optional[int]:
        """Return the index of the oldest message eligible for dropping.

        System messages are never dropped.  Tool messages from high-priority
        tools (build/test diagnostics) are also skipped in the first pass so
        that critical error output survives compression as long as possible.
        If no non-priority candidate exists, fall back to any non-system
        message to guarantee progress.
        """
        # First pass: prefer dropping non-system, non-high-priority messages.
        for index, message in enumerate(messages):
            if message.get("role") == "system":
                continue
            tool_calls = message.get("tool_calls") or []
            if message.get("role") == "assistant" and any(
                str(((call or {}).get("function") or {}).get("name") or "") in _HIGH_PRIORITY_TOOLS
                for call in tool_calls
                if isinstance(call, dict)
            ):
                continue
            tool_name = message.get("name") or ""
            if message.get("role") == "tool" and tool_name in _HIGH_PRIORITY_TOOLS:
                continue
            return index
        # Second pass (fallback): drop any non-system message.
        for index, message in enumerate(messages):
            if message.get("role") != "system":
                return index
        return None

    def _trim_chunk_indices(self, messages: List[Dict[str, Any]], index: int) -> List[int]:
        message = messages[index]
        if message.get("role") == "assistant":
            expected_call_ids = set(
                str(item.get("id") or "").strip()
                for item in (message.get("tool_calls") or [])
                if isinstance(item, dict) and str(item.get("id") or "").strip()
            )
            if not expected_call_ids:
                return [index]
            discard = set([index])
            for idx in range(index + 1, len(messages)):
                current = messages[idx]
                if current.get("role") == "system":
                    continue
                if current.get("role") != "tool":
                    break
                call_id = str(current.get("tool_call_id") or "").strip()
                if call_id in expected_call_ids:
                    discard.add(idx)
                    expected_call_ids.discard(call_id)
                    if not expected_call_ids:
                        break
            return sorted(discard)
        if message.get("role") == "tool":
            call_id = str(message.get("tool_call_id") or "").strip()
            if call_id:
                owner_index = self._find_tool_call_owner_index(messages, call_id, index)
                if owner_index is not None and owner_index != index:
                    return self._trim_chunk_indices(messages, owner_index)
        return [index]

    def _find_tool_call_owner_index(
        self,
        messages: List[Dict[str, Any]],
        tool_call_id: str,
        upto_index: int,
    ) -> Optional[int]:
        for index in range(upto_index - 1, -1, -1):
            message = messages[index]
            if message.get("role") != "assistant":
                continue
            for call in (message.get("tool_calls") or []):
                if not isinstance(call, dict):
                    continue
                if str(call.get("id") or "").strip() == tool_call_id:
                    return index
        return None

    def _analyze_context(self, session: Session) -> Dict[str, Any]:
        tool_request_tokens = 0
        tool_result_tokens = 0
        duplicate_file_read_tokens = 0
        file_counts = {}
        seen_reads = {}
        replacement_count = 0
        for turn in session.turns:
            for action in turn.actions:
                tool_request_tokens += self.token_estimator.estimate_text(json.dumps(action.arguments, ensure_ascii=False))
            for observation in turn.observations:
                tool_result_tokens += self.token_estimator.estimate_text(json.dumps(observation.to_dict(), ensure_ascii=False))
                if not isinstance(observation.data, dict):
                    continue
                path = observation.data.get("path")
                if isinstance(path, str) and path:
                    file_counts[path] = file_counts.get(path, 0) + 1
                artifact_refs = [value for key, value in observation.data.items() if key.endswith("_artifact_ref") and value]
                if artifact_refs:
                    replacement_count += 1
                if observation.tool_name == "read_file" and isinstance(path, str) and path:
                    current_tokens = self.token_estimator.estimate_text(str(observation.data.get("content") or ""))
                    previous = seen_reads.get(path)
                    if previous is not None:
                        duplicate_file_read_tokens += min(previous, current_tokens)
                    else:
                        seen_reads[path] = current_tokens
        ranked = sorted(file_counts.items(), key=lambda item: (-item[1], item[0]))
        return {
            "tool_request_tokens": tool_request_tokens,
            "tool_result_tokens": tool_result_tokens,
            "duplicate_file_read_tokens": duplicate_file_read_tokens,
            "top_hot_files": [{"path": path, "count": count} for path, count in ranked[:5]],
            "artifact_replacement_count": replacement_count,
            "resume_replay_hits": 1 if session.latest_compact_boundary() is not None else 0,
        }


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


def _single_line(text: str) -> str:
    return " ".join(text.split())
