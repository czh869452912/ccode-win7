from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from embedagent.project_memory import ProjectMemoryStore
from embedagent.session import Observation, Session


@dataclass
class IntelligenceEvidence:
    provider: str
    title: str
    content: str
    priority: int = 50
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkspaceIntelligenceProvider(object):
    name = "provider"

    def collect(
        self,
        session: Session,
        mode_name: str,
        tools: Any,
        project_memory: Optional[ProjectMemoryStore] = None,
    ) -> List[IntelligenceEvidence]:
        return []


class WorkingSetProvider(WorkspaceIntelligenceProvider):
    name = "working_set"

    def collect(self, session: Session, mode_name: str, tools: Any, project_memory: Optional[ProjectMemoryStore] = None) -> List[IntelligenceEvidence]:
        modified = []
        seen = set()
        for turn in reversed(session.turns):
            for observation in reversed(turn.observations):
                if observation.tool_name not in ("write_file", "edit_file"):
                    continue
                if not isinstance(observation.data, dict):
                    continue
                path = str(observation.data.get("path") or "")
                if not path or path in seen:
                    continue
                seen.add(path)
                modified.append(path)
                if len(modified) >= 6:
                    break
            if len(modified) >= 6:
                break
        if not modified:
            return []
        return [
            IntelligenceEvidence(
                provider=self.name,
                title="Recent Modified Files",
                content="最近修改文件：%s" % ", ".join(modified),
                priority=95,
                tags=["working_set", mode_name],
                metadata={"paths": modified},
            )
        ]


class ProjectMemoryProvider(WorkspaceIntelligenceProvider):
    name = "project_memory"

    def collect(self, session: Session, mode_name: str, tools: Any, project_memory: Optional[ProjectMemoryStore] = None) -> List[IntelligenceEvidence]:
        if project_memory is None:
            return []
        content = project_memory.build_system_message(mode_name, 1200)
        if not content:
            return []
        return [
            IntelligenceEvidence(
                provider=self.name,
                title="Project Memory",
                content=content,
                priority=90,
                tags=["project_memory", mode_name],
            )
        ]


class RecipeProvider(WorkspaceIntelligenceProvider):
    name = "recipes"

    def collect(self, session: Session, mode_name: str, tools: Any, project_memory: Optional[ProjectMemoryStore] = None) -> List[IntelligenceEvidence]:
        if not hasattr(tools, "workspace_recipes"):
            return []
        payload = tools.workspace_recipes() or {}
        items = payload.get("items") if isinstance(payload, dict) else []
        if not isinstance(items, list) or not items:
            return []
        ranked = self._rank_items(mode_name, items)
        selected = []
        for item in ranked[:4]:
            if not isinstance(item, dict):
                continue
            selected.append(
                "[%s] %s" % (
                    str(item.get("tool_name") or ""),
                    str(item.get("id") or item.get("label") or ""),
                )
            )
        if not selected:
            return []
        return [
            IntelligenceEvidence(
                provider=self.name,
                title="Active Recipes",
                content="工作区 recipe：%s" % "; ".join(selected),
                priority=85 if mode_name in ("code", "verify", "debug") else 55,
                tags=["recipe", mode_name],
                metadata={"count": len(items)},
            )
        ]

    def _rank_items(self, mode_name: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        preferred = {
            "verify": {"run_tests": 0, "run_clang_tidy": 1, "run_clang_analyzer": 2, "collect_coverage": 3, "compile_project": 4},
            "code": {"compile_project": 0, "run_tests": 1, "run_clang_tidy": 2},
            "debug": {"run_tests": 0, "compile_project": 1, "run_clang_tidy": 2, "run_clang_analyzer": 3},
            "explore": {"compile_project": 0, "run_tests": 1},
            "spec": {"compile_project": 0, "run_tests": 1},
        }.get(mode_name, {})
        return sorted(
            items,
            key=lambda item: (
                preferred.get(str(item.get("tool_name") or ""), 99),
                str(item.get("id") or ""),
            ),
        )


class CtagsProvider(WorkspaceIntelligenceProvider):
    name = "ctags"

    def collect(self, session: Session, mode_name: str, tools: Any, project_memory: Optional[ProjectMemoryStore] = None) -> List[IntelligenceEvidence]:
        runtime = tools.runtime_environment_snapshot() if hasattr(tools, "runtime_environment_snapshot") else {}
        roots = runtime.get("resolved_tool_roots") if isinstance(runtime, dict) else {}
        ctags_path = str((roots or {}).get("ctags_exe") or "")
        tags_file = os.path.join(tools.workspace, "tags")
        if os.path.isfile(tags_file):
            entries = _load_ctags_entries(tags_file, limit=16)
            focus_paths = _focus_paths_from_session(session)
            if focus_paths:
                entries.sort(key=lambda item: (0 if item["path"] in focus_paths else 1, item["path"], item["name"]))
            entries = entries[:5]
            if entries:
                rendered = []
                for item in entries:
                    rendered.append("%s -> %s (%s)" % (item["name"], item["path"], item["kind"]))
                content = "关键符号：%s" % "; ".join(rendered)
            else:
                content = "检测到 tags 文件：%s" % os.path.relpath(tags_file, tools.workspace).replace(os.sep, "/")
        elif ctags_path:
            content = "ctags 可用：%s；当前还没有预生成 tags 文件。" % ctags_path
        else:
            content = "ctags 尚未就绪；符号情报会退化到 grep/诊断。"
        return [
            IntelligenceEvidence(
                provider=self.name,
                title="Symbol Intelligence",
                content=content,
                priority=80 if mode_name in ("code", "debug") else 40,
                tags=["symbol", mode_name],
                metadata={"ctags_available": bool(ctags_path), "tags_file": os.path.isfile(tags_file), "parsed_tags": bool(os.path.isfile(tags_file) and _load_ctags_entries(tags_file, limit=1)), "focus_paths": focus_paths if os.path.isfile(tags_file) else []},
            )
        ]


class DiagnosticsProvider(WorkspaceIntelligenceProvider):
    name = "diagnostics"

    def collect(self, session: Session, mode_name: str, tools: Any, project_memory: Optional[ProjectMemoryStore] = None) -> List[IntelligenceEvidence]:
        evidence = []
        focus_paths = set(_focus_paths_from_session(session))
        seen_keys = set()
        observations = list(reversed(_all_observations(session)))
        observations.sort(
            key=lambda observation: (
                0 if _observation_primary_path(observation) in focus_paths else 1,
                0 if observation.tool_name in ("run_tests", "compile_project", "run_clang_tidy", "run_clang_analyzer") else 1,
            )
        )
        for observation in observations:
            if observation.tool_name not in (
                "compile_project",
                "run_tests",
                "run_clang_tidy",
                "run_clang_analyzer",
                "collect_coverage",
                "report_quality",
            ):
                continue
            if not isinstance(observation.data, dict):
                continue
            detail = _diagnostic_detail(observation)
            if not detail:
                continue
            primary_path = _observation_primary_path(observation)
            key = "%s|%s|%s" % (observation.tool_name, primary_path, detail)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            evidence.append(
                IntelligenceEvidence(
                    provider=self.name,
                    title="Recent Diagnostics",
                    content=detail,
                    priority=100 if mode_name in ("code", "debug", "verify") else 60,
                    tags=["diagnostic", observation.tool_name, mode_name],
                    metadata={"tool_name": observation.tool_name, "focus_match": primary_path in focus_paths, "path": primary_path},
                )
            )
            if len(evidence) >= 2:
                break
        return evidence


class GitStateProvider(WorkspaceIntelligenceProvider):
    name = "git"

    def collect(self, session: Session, mode_name: str, tools: Any, project_memory: Optional[ProjectMemoryStore] = None) -> List[IntelligenceEvidence]:
        if mode_name not in ("explore", "spec", "code", "debug"):
            return []
        observation = tools.execute("git_status", {"path": "."})
        if not isinstance(observation.data, dict):
            return []
        branch = str(observation.data.get("branch") or "")
        entries = observation.data.get("entries") if isinstance(observation.data.get("entries"), list) else []
        return [
            IntelligenceEvidence(
                provider=self.name,
                title="Git Workspace State",
                content="Git 分支 `%s`，脏文件 %s 个。" % (branch or "-", len(entries)),
                priority=50,
                tags=["git", mode_name],
                metadata={"branch": branch, "dirty_count": len(entries)},
            )
        ]


class LlspBackend(object):
    def collect(self, workspace: str, session: Session, mode_name: str) -> List[Dict[str, Any]]:
        return []


class LlspProvider(WorkspaceIntelligenceProvider):
    name = "llsp"

    def __init__(self, backend: Optional[LlspBackend] = None) -> None:
        self.backend = backend

    def collect(self, session: Session, mode_name: str, tools: Any, project_memory: Optional[ProjectMemoryStore] = None) -> List[IntelligenceEvidence]:
        if self.backend is not None:
            items = self.backend.collect(tools.workspace, session, mode_name) or []
            evidence = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                evidence.append(
                    IntelligenceEvidence(
                        provider=self.name,
                        title=str(item.get("title") or "LLSP Evidence"),
                        content=str(item.get("content") or ""),
                        priority=int(item.get("priority") or 75),
                        tags=["llsp", mode_name],
                        metadata=dict(item.get("metadata") or {}),
                    )
                )
            if evidence:
                return evidence
        return [
            IntelligenceEvidence(
                provider=self.name,
                title="LLSP Provider",
                content="LLSP provider 已预留接口，当前使用空实现并自动退化到 ctags + grep + diagnostics。",
                priority=30,
                tags=["llsp", "contract"],
                metadata={"available": False},
            )
        ]


class WorkspaceIntelligenceBroker(object):
    def __init__(self, providers: Optional[List[WorkspaceIntelligenceProvider]] = None) -> None:
        self.providers = providers or [
            WorkingSetProvider(),
            ProjectMemoryProvider(),
            RecipeProvider(),
            CtagsProvider(),
            DiagnosticsProvider(),
            GitStateProvider(),
            LlspProvider(),
        ]

    def collect(
        self,
        session: Session,
        mode_name: str,
        tools: Any,
        project_memory: Optional[ProjectMemoryStore] = None,
    ) -> List[IntelligenceEvidence]:
        collected = []
        for provider in self.providers:
            collected.extend(provider.collect(session, mode_name, tools, project_memory))
        collected = self._filter_for_mode(mode_name, collected)
        collected.sort(key=lambda item: (-int(item.priority or 0), item.provider, item.title))
        return collected

    def render_system_message(
        self,
        session: Session,
        mode_name: str,
        tools: Any,
        project_memory: Optional[ProjectMemoryStore] = None,
        limit: int = 3,
        char_limit: int = 1600,
    ) -> str:
        evidence = self.collect(session, mode_name, tools, project_memory)[:limit]
        if not evidence:
            return ""
        lines = ["以下是当前工作区的工程情报，仅供当前任务参考："]
        for item in evidence:
            lines.append("- %s: %s" % (item.title, item.content))
        message = "\n".join(lines)
        return message[:char_limit]

    def _filter_for_mode(self, mode_name: str, evidence: List[IntelligenceEvidence]) -> List[IntelligenceEvidence]:
        allowed_tags = {
            "explore": {"project_memory", "git", "recipe", "llsp", "symbol"},
            "spec": {"project_memory", "git", "recipe", "llsp", "symbol"},
            "code": {"working_set", "project_memory", "recipe", "symbol", "diagnostic", "llsp"},
            "debug": {"working_set", "project_memory", "recipe", "symbol", "diagnostic", "git", "llsp"},
            "verify": {"project_memory", "recipe", "diagnostic", "llsp"},
        }.get(mode_name)
        if not allowed_tags:
            return evidence
        filtered = []
        for item in evidence:
            if not item.tags:
                filtered.append(item)
                continue
            if any(tag in allowed_tags for tag in item.tags):
                filtered.append(item)
        return filtered


def _all_observations(session: Session) -> List[Observation]:
    observations = []
    for turn in session.turns:
        observations.extend(turn.observations)
    return observations


def _diagnostic_detail(observation: Observation) -> str:
    if not isinstance(observation.data, dict):
        return ""
    data = observation.data
    if observation.tool_name == "run_tests":
        summary = data.get("test_summary") if isinstance(data.get("test_summary"), dict) else {}
        total = int(summary.get("total") or 0)
        failed = int(summary.get("failed") or 0)
        return "最近测试：total=%s, failed=%s。" % (total, failed)
    if observation.tool_name == "collect_coverage":
        summary = data.get("coverage_summary") if isinstance(data.get("coverage_summary"), dict) else {}
        line_cov = summary.get("line_coverage")
        if line_cov is not None:
            return "最近覆盖率：line coverage %.2f%%。" % float(line_cov)
        return ""
    diagnostics = data.get("diagnostics") if isinstance(data.get("diagnostics"), list) else []
    if diagnostics:
        first = diagnostics[0] if isinstance(diagnostics[0], dict) else {}
        return "%s:%s:%s %s" % (
            first.get("file") or "?",
            first.get("line") or 1,
            first.get("column") or 1,
            first.get("message") or observation.error or "",
        )
    if observation.error:
        return "%s: %s" % (observation.tool_name, observation.error)
    return ""


def _observation_primary_path(observation: Observation) -> str:
    if not isinstance(observation.data, dict):
        return ""
    direct = observation.data.get("path")
    if isinstance(direct, str) and direct:
        return direct.replace("\\", "/")
    diagnostics = observation.data.get("diagnostics") if isinstance(observation.data.get("diagnostics"), list) else []
    for item in diagnostics:
        if not isinstance(item, dict):
            continue
        path = item.get("file") or item.get("path")
        if isinstance(path, str) and path:
            return path.replace("\\", "/")
    return ""


def _load_ctags_entries(path: str, limit: int = 5) -> List[Dict[str, str]]:
    entries = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("!_TAG_"):
                    continue
                parts = line.split("\t")
                if len(parts) < 4:
                    continue
                name = parts[0].strip()
                file_path = parts[1].strip().replace("\\", "/")
                rest = parts[3:]
                kind = ""
                for token in rest:
                    token = token.strip()
                    if token.startswith("kind:"):
                        kind = token.split(":", 1)[1].strip()
                        break
                    if len(token) == 1:
                        kind = token
                        break
                entries.append(
                    {
                        "name": name,
                        "path": file_path,
                        "kind": kind or "?",
                    }
                )
                if len(entries) >= limit:
                    break
    except OSError:
        return []
    return entries


def _focus_paths_from_session(session: Session) -> List[str]:
    seen = set()
    paths = []
    for observation in reversed(_all_observations(session)):
        if not isinstance(observation.data, dict):
            continue
        direct = observation.data.get("path")
        if isinstance(direct, str) and direct and direct not in seen:
            seen.add(direct)
            paths.append(direct.replace("\\", "/"))
        diagnostics = observation.data.get("diagnostics") if isinstance(observation.data.get("diagnostics"), list) else []
        for item in diagnostics:
            if not isinstance(item, dict):
                continue
            path = item.get("file") or item.get("path")
            if isinstance(path, str) and path and path not in seen:
                seen.add(path)
                paths.append(path.replace("\\", "/"))
    return paths[:8]
