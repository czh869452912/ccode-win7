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
        selected = []
        for item in items[:4]:
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


class CtagsProvider(WorkspaceIntelligenceProvider):
    name = "ctags"

    def collect(self, session: Session, mode_name: str, tools: Any, project_memory: Optional[ProjectMemoryStore] = None) -> List[IntelligenceEvidence]:
        runtime = tools.runtime_environment_snapshot() if hasattr(tools, "runtime_environment_snapshot") else {}
        roots = runtime.get("resolved_tool_roots") if isinstance(runtime, dict) else {}
        ctags_path = str((roots or {}).get("ctags_exe") or "")
        tags_file = os.path.join(tools.workspace, "tags")
        if os.path.isfile(tags_file):
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
                metadata={"ctags_available": bool(ctags_path), "tags_file": os.path.isfile(tags_file)},
            )
        ]


class DiagnosticsProvider(WorkspaceIntelligenceProvider):
    name = "diagnostics"

    def collect(self, session: Session, mode_name: str, tools: Any, project_memory: Optional[ProjectMemoryStore] = None) -> List[IntelligenceEvidence]:
        evidence = []
        for observation in reversed(_all_observations(session)):
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
            evidence.append(
                IntelligenceEvidence(
                    provider=self.name,
                    title="Recent Diagnostics",
                    content=detail,
                    priority=100 if mode_name in ("code", "debug", "verify") else 60,
                    tags=["diagnostic", observation.tool_name, mode_name],
                    metadata={"tool_name": observation.tool_name},
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


class LlspProvider(WorkspaceIntelligenceProvider):
    name = "llsp"

    def collect(self, session: Session, mode_name: str, tools: Any, project_memory: Optional[ProjectMemoryStore] = None) -> List[IntelligenceEvidence]:
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
